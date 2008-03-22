###
# Copyright (c) 2007, Ben Firshman
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import time

import supybot.conf as conf
import supybot.ircdb as ircdb
import supybot.utils as utils
import supybot.world as world
from supybot.commands import *
import supybot.ircmsgs as ircmsgs
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.registry as registry
import supybot.callbacks as callbacks


class Clone(callbacks.Plugin):
    """This plugin provides a set of commands for managing, adding and 
    removing clones on a network."""
    def add(self, irc, msg, args, num, otherIrc):
        """[<num>] [<network>]
        
        Adds <num> clones to <network>. If <num> is not specified, it
        defaults to 1. If <network> is not specified, the current network is
        assumed."""
        if num is None:
            num = 1
        networkGroup = conf.supybot.networks.get(otherIrc.network)
        Owner = irc.getCallback('Owner')
        for i in range(num):
            if not Owner._connectClone(otherIrc.network, 
                    networkGroup.numberOfClones()):
                irc.replyError()
                return
            networkGroup.numberOfClones.setValue( \
                    networkGroup.numberOfClones() + 1)
        
        irc.replySuccess(utils.str.format('Connection for %n on %s initiated',
                         (num, 'clone'), otherIrc.network))
    add = wrap(add, ['owner', additional('int'), 'networkIrc'])

    def remove(self, irc, msg, args, num, otherIrc, quitMsg):
        """[<num>] [<network>] [<quit message>]
        
        Removes <num> clones from <network>. If <num> is not specified, it
        defaults to 1. If <network> is not specified, the current network is
        assumed. If <quit message> is given, quits the network with the given 
        quit message."""
        if num is None:
            num = 1
        quitMsg = quitMsg or conf.supybot.plugins.Owner.quitMsg() or msg.nick
        networkGroup = conf.supybot.networks.get(otherIrc.network)
        cloneIrcs = world.getIrcs(otherIrc.network)
        if len(cloneIrcs) <= 1:
            irc.error('There is only one clone left in this network, use ' \
                      'the Network plugin instead.')
            return
        if len(cloneIrcs) - num <= 0:
            irc.error('Removing that many clones will leave us with no ' \
                      'clones on the network. Try removing fewer.')
            return
        currentIrcKilled = False
        for i in range(num):
            ircToKill = cloneIrcs[networkGroup.numberOfClones() - 1]
            ircToKill.queueMsg(ircmsgs.quit(quitMsg))
            ircToKill.die()
            networkGroup.numberOfClones.setValue( \
                    networkGroup.numberOfClones() - 1)
            if ircToKill == irc:
                currentIrcKilled = True
        if not currentIrcKilled:
            irc.replySuccess(utils.str.format('%n disconnected on %s',
                             (num, 'clone'), otherIrc.network))
    remove = wrap(remove, ['owner', additional('int'), 'networkIrc', \
                    additional('text')])
    
    def reconnect(self, irc, msg, args, clone, otherIrc, quitMsg):
        """[<clone>] [<network>] [<quit message>]

        Disconnects and then reconnects <clone> on <network>. If no clone is 
        given, the current clone is assumed. If no network is given,
        disconnects and then reconnects to the network the command was given
        on.  If no quit message is given, uses the configured one
        (supybot.plugins.Owner.quitMsg) or the nick of the person giving the
        command.
        """
        quitMsg = quitMsg or conf.supybot.plugins.Owner.quitMsg() or msg.nick
        if clone is None:
            clone = otherIrc.clone
        cloneIrcs = world.getIrcs(otherIrc.network)
        if not cloneIrcs.has_key(clone):
            irc.error('Clone specified does not exist on this network')
        cloneIrcs[clone].queueMsg(ircmsgs.quit(quitMsg))
        cloneIrcs[clone].driver.reconnect()
        if cloneIrcs[clone] != irc:
            # No need to reply if we're reconnecting ourselves.
            irc.replySuccess()
    reconnect = wrap(reconnect, ['owner', additional('int'), 'networkIrc', \
                                 additional('text')])
    
    def announce(self, irc, msg, args, text):
        """<text>

        Sends <text> to all channels all the clones are currently on and not
        lobotomized in.
        """
        u = ircdb.users.getUser(msg.prefix)
        text = 'Announcement from my owner (%s): %s' % (u.name, text)
        
        cloneIrcs = world.getIrcs(irc.network)
        for i in cloneIrcs.values():
            for channel in i.state.channels:
                c = ircdb.channels.getChannel(channel)
                if not c.lobotomized:
                    i.queueMsg(ircmsgs.privmsg(channel, text))
        irc.noReply()
    announce = wrap(announce, ['owner', 'text'])
    
    def _join(self, irc, msg, args, channel, key):
        if not irc.isChannel(channel):
            irc.errorInvalid('channel', channel, Raise=True)
        networkGroup = conf.supybot.networks.get(irc.network)
        cloneIrcs = world.getIrcs(irc.network)
        Admin = irc.getCallback('Admin')
        chosenIrc = None
        # have we joined this channel in the past?
        try:
            clone = networkGroup.channels.clone.get(channel).value
            i = cloneIrcs[clone]
            if networkGroup.maxChannels():
                maxchannels = networkGroup.maxChannels()
            else:
                maxchannels = i.state.supported.get('maxchannels',
                                sys.maxint)
            if str(i.clone) not in networkGroup.protectedClones() \
                    and len(i.state.channels) + 1 <= maxchannels:
                chosenIrc = i
        except registry.NonExistentRegistryEntry:
            pass
        except KeyError:
            pass
        if not chosenIrc:
            # FIXME: HACK: the Irc object runs into an infinite loop with 
            # comparision to None. this is a quick fix, I'll look into why
            # later
            for i in cloneIrcs.values():
                if networkGroup.maxChannels():
                    maxchannels = networkGroup.maxChannels()
                else:
                    maxchannels = i.state.supported.get('maxchannels',
                                    sys.maxint)
                if str(i.clone) not in networkGroup.protectedClones() \
                        and len(i.state.channels) + 1 <= maxchannels \
                        and (not chosenIrc or 
                        len(i.state.channels) < 
                        len(chosenIrc.state.channels)):
                    chosenIrc = i
            if not chosenIrc:
                irc.error("There isn't a clone with any space for joining. "
                          "Either add more clones, free up some clones in "
                          "the protectedClones setting or part some channels",
                          Raise=True)
        networkGroup.channels().add(channel)
        networkGroup.channels.clone.get(channel).setValue(chosenIrc.clone)
        if key:
            networkGroup.channels.key.get(channel).setValue(key)
        chosenIrc.queueMsg(networkGroup.channels.join(channel))
        irc.replySuccess("Initiated join for clone %s." % chosenIrc.clone)
        Admin.joins[channel] = (irc, msg)
        
    def join(self, irc, msg, args, channel, key):
        """<channel> [<key>]
        
        Finds the clone with the fewest channels (taking into account 
        configured protected clones) and tells it to join the given channel.
        If <key> is given, it is used when attempting to join the channel."""
        return self._join(irc, msg, args, channel, key)
        
    join = wrap(join, ['admin', 'validChannel', additional('something')])
    
    def _part(self, irc, msg, args, channel, reason):
        chosenIrcs = []
        if channel is None:
            if irc.isChannel(msg.args[0]):
                channel = msg.args[0]
                chosenIrcs.append(irc)
            else:
                irc.error(Raise=True)
        else:
            cloneIrcs = world.getIrcs(irc.network)
            for i in cloneIrcs.values():
                if channel in i.state.channels:
                    chosenIrcs.append(i)
        try:
            network = conf.supybot.networks.get(irc.network)
            network.channels().remove(channel)
        except KeyError:
            pass
        if not chosenIrcs:
            irc.error('I\'m not in %s.' % channel, Raise=True)
        for i in chosenIrcs:
            i.queueMsg(ircmsgs.part(channel, reason or msg.nick))
        irc.noReply()
        
    def part(self, irc, msg, args, channel, reason):
        """[<channel>] [<reason>]

        Finds the clone that is in <channel> and tells is to part it  
        <channel> is only necessary if you want the bot to part a channel 
        other than the current channel.  If <reason> is specified, use it as 
        the part message.
        """
        return self._part(irc, msg, args, channel, reason)
        
    part = wrap(part, ['admin', optional('validChannel'), additional('text')])
    
    def status(self, irc, msg, args):
        """takes no arguments

        Returns the status of each clone.
        """
        L = []
        cloneIrcs = world.getIrcs(irc.network)
        for i in cloneIrcs.values():
            s = "%s: " % i.clone
            if i.afterConnect:
                s += utils.str.format("%n",
                        (len(i.state.channels.keys()), 'chan'))
            elif not i.driver:
                s += "No driver"
            elif i.driver.connected:
                s += "Connecting..."
            elif hasattr(i.driver, "nextReconnectTime") \
                    and i.driver.nextReconnectTime:
                s += "%ss to next reconnect" \
                        % int(i.driver.nextReconnectTime - time.time())
                if hasattr(i.driver, "lastReconnectReason"):
                    s += " (%s)" % i.driver.lastReconnectReason
            else:
                s += "Not connected"
                if hasattr(i.driver, "lastReconnectReason"):
                    s += " (%s)" % i.driver.lastReconnectReason
            L.append(s)
        irc.reply(format('%L', L))
    status = wrap(status, ['admin'])
    
Class = Clone


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
