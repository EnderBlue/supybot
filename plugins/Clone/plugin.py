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

import supybot.conf as conf
import supybot.utils as utils
import supybot.world as world
from supybot.commands import *
import supybot.ircmsgs as ircmsgs
import supybot.plugins as plugins
import supybot.ircutils as ircutils
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
            try:
                Owner._connectClone(otherIrc.network, \
                        networkGroup.numberOfClones())
            except ValueError, e:
                irc.error('Error adding clone %s: %s' % (clone, e))
                return
            networkGroup.numberOfClones.setValue( \
                    networkGroup.numberOfClones() + 1)
        if num == 1:
            irc.replySuccess('Connection initiated for clone %s on %s' % \
                    (networkGroup.numberOfClones() - 1, otherIrc.network))
        else:
            irc.replySuccess('Connection for %s clones on %s initiated' % \
                             (num, otherIrc.network))
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
            if num == 1:
                irc.replySuccess('Clone %s on %s has been disconnected' % \
                        (networkGroup.numberOfClones(), otherIrc.network))
            else:
                irc.replySuccess('%s clones disconnected on %s' % \
                                 (num, otherIrc.network))
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
        if cloneIrcs[clone] != irc:
            # No need to reply if we're reconnecting ourselves.
            irc.replySuccess()
    reconnect = wrap(reconnect, ['owner', additional('int'), 'networkIrc', \
                                 additional('text')])
Class = Clone


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
