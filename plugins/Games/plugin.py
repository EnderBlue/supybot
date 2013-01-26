###
# Copyright (c) 2003-2005, Jeremiah Fincher
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

import re
import random
import time

import supybot.utils as utils
import supybot.world as world
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks


class Games(callbacks.Plugin):
            
    def __init__(self, irc):
        self.__parent = super(Games, self)
        self.__parent.__init__(irc)
        self.rng = random.Random()
        self.rng.seed()
        self._chamberSizeMin = 0
        self._chamberSizeMax = 6
        self._chamberMin = 0
        self._chamberMax = 1
        self._bulletMin = 2
        self._bulletMax = 3
        self._rouletteChamber = {}
        self._rouletteBullet = {}
        
    def coin(self, irc, msg, args):
        """takes no arguments

        Flips a coin and returns the result.
        """
        if random.randrange(0, 2):
            irc.reply('heads')
        else:
            irc.reply('tails')
    coin = wrap(coin)

    def dice(self, irc, msg, args, m):
        """<dice>d<sides>

        Rolls a die with <sides> number of sides <dice> times.
        For example, 2d6 will roll 2 six-sided dice; 10d10 will roll 10
        ten-sided dice.
        """
        (dice, sides) = utils.iter.imap(int, m.groups())
        if dice > 6:
            irc.error('You can\'t roll more than 6 dice.')
        elif sides > 100:
            irc.error('Dice can\'t have more than 100 sides.')
        elif sides < 3:
            irc.error('Dice can\'t have fewer than 3 sides.')
        else:
            L = [0] * dice
            for i in xrange(dice):
                L[i] = random.randrange(1, sides+1)
            irc.reply(format('%L', [str(x) for x in L]))
    _dicere = re.compile(r'^(\d+)d(\d+)$')
    dice = wrap(dice, [('matches', _dicere,
                        'Dice must be of the form <dice>d<sides>')])

    # The list of words and algorithm are pulled straight the mozbot
    # MagicEightBall.bm module: http://tinyurl.com/7ytg7
    _responses = {'positive': ['It is possible.', 'Yes!', 'Of course.',
                               'Naturally.', 'Obviously.', 'It shall be.',
                               'The outlook is good.', 'It is so.',
                               'One would be wise to think so.',
                               'The answer is certainly yes.'],
                  'negative': ['In your dreams.', 'I doubt it very much.',
                               'No chance.', 'The outlook is poor.',
                               'Unlikely.', 'About as likely as pigs flying.',
                               'You\'re kidding, right?', 'NO!', 'NO.', 'No.',
                               'The answer is a resounding no.', ],
                  'unknown' : ['Maybe...', 'No clue.', '_I_ don\'t know.',
                               'The outlook is hazy, please ask again later.',
                               'What are you asking me for?', 'Come again?',
                               'You know the answer better than I.',
                               'The answer is def-- oooh! shiny thing!'],
                 }

    def _checkTheBall(self, questionLength):
        if questionLength % 3 == 0:
            category = 'positive'
        elif questionLength % 3 == 1:
            category = 'negative'
        else:
            category = 'unknown'
        return utils.iter.choice(self._responses[category])

    def eightball(self, irc, msg, args, text):
        """[<question>]

        Ask a question and the answer shall be provided.
        """
        if text:
            irc.reply(self._checkTheBall(len(text)))
        else:
            irc.reply(self._checkTheBall(random.randint(0, 2)))
    eightball = wrap(eightball, [additional('text')])

    #def roulette(self, irc, msg, args, spin):
    def roulette(self, irc, msg, args, nick):
        """[spin|nick]

        Fires the revolver.  If the bullet was in the chamber, you're dead.
        Tell me to spin the chambers and I will.
        """
        
        chamberSize = self._chamberSizeMax
        #if spin:
        channel = msg.args[0]
        
        if channel not in self._rouletteChamber:
            self._rouletteChamber[channel] = self.rng.randrange(self._chamberMin, self._chamberMax)
            self._rouletteBullet[channel] = self.rng.randrange(self._bulletMin, self._bulletMax)
        
        if nick.lower() == 'spin':
            self._rouletteBullet[channel] = self.rng.randrange(0, chamberSize)
            irc.reply('*SPIN* Are you feeling lucky?', prefixNick=False)
            return
        
        nickFound = False
        if nick.lower() == '':
            nick = msg.nick
            nickFound = True
        elif nick.lower() == 'random':
            nicks = list(irc.state.channels[channel].users)
            if len(nicks) >= 2:
                nickCount = 0
                nick = self.rng.choice(nicks)
                while nickCount < 99 and nick in self.registryValue('exclusions', msg.args[0]):
                    nick = self.rng.choice(nicks)
                    nickCount += 1
                    
                if nickCount >= 98:
                    nick = msg.nick
                
            else:
                nick = msg.nick
                
            nickFound = True
        elif nick.lower() == msg.nick.lower():
            nick = nick
            nickFound = True
        else:
            for nickTry in self.registryValue('exclusions', channel):
                if nick.lower() == nickTry.lower():
                    irc.sendMsg(ircmsgs.action(channel, '%s rips the pistol out of your hand and points it at you!' % nick))
                    nick = msg.nick
                    nickFound = True
                    break
            if not nickFound:
                for nickTry in list(irc.state.channels[channel].users):
                    if nick.lower() == nickTry.lower():
                        nick = nick
                        nickFound = True
                        break
        if not nickFound:
            nick = msg.nick
            irc.reply('%s: You didn\'t point the pistol at a real Nick, so it defaults to you :)' % nick, prefixNick=False)
            
        if self._rouletteChamber[channel] == self._rouletteBullet[channel]:
            self._rouletteChamber[channel] = self.rng.randrange(self._chamberMin, self._chamberMax)
            self._rouletteBullet[channel] = self.rng.randrange(self._bulletMin, self._bulletMax)
            if irc.nick in irc.state.channels[channel].ops:
                irc.sendMsg(ircmsgs.privmsg(channel, '%s: BANG!!' % nick))
                irc.queueMsg(ircmsgs.kick(channel, nick, 'BANG!'))
            else:
                irc.reply('*BANG* Hey, who put a blank in here?!',
                          prefixNick=False)
            irc.reply('reloads and spins the chambers.', action=True)
        else:
            irc.sendMsg(ircmsgs.privmsg(channel, '%s: *click*' % nick))
            self._rouletteChamber[channel] += 1
            self._rouletteChamber[channel] %= chamberSize
    #roulette = wrap(roulette, ['public', additional(('literal', 'spin'))])
    roulette = wrap(roulette, ['public', additional('text','')])

    def randroulette(self, irc, msg, args, channel):
        """takes no arguments

        Keeps firing the revolver at a random person in the channel 
        until it fires.
        """
        
        chamberSize = self._chamberSizeMax
        nicks = list(irc.state.channels[channel].users)
        
        if channel not in self._rouletteChamber:
            self._rouletteChamber[channel] = self.rng.randrange(self._chamberMin, self._chamberMax)
            self._rouletteBullet[channel] = self.rng.randrange(self._bulletMin, self._bulletMax)
        
        while True:
            nickCount = 0
            nick = self.rng.choice(nicks)
            while nickCount < 99 and nick in self.registryValue('exclusions', channel):
                nick = self.rng.choice(nicks)
                nickCount += 1
                
            if nickCount >= 96:
                nick = msg.nick
            
            if self._rouletteChamber[channel] == self._rouletteBullet[channel]:
                break
            else:
                irc.sendMsg(ircmsgs.privmsg(channel, '%s: *click*' % nick))
                self._rouletteChamber[channel] += 1
                self._rouletteChamber[channel] %= chamberSize
        
        self._rouletteChamber[channel] = self.rng.randrange(self._chamberMin, self._chamberMax)
        self._rouletteBullet[channel] = self.rng.randrange(self._bulletMin, self._bulletMax)
        if irc.nick in irc.state.channels[channel].ops:
            irc.sendMsg(ircmsgs.privmsg(channel, '%s: BANG!!' % nick))
            irc.queueMsg(ircmsgs.kick(channel, nick, 'BANG!'))
        else:
            irc.reply('*BANG* Hey, who put a blank in here?!',
                      prefixNick=False)
        irc.reply('reloads and spins the chambers.', action=True)
        
    randroulette = wrap(randroulette, ['public', 'Channel'])
    
    def monologue(self, irc, msg, args, channel):
        """[<channel>]

        Returns the number of consecutive lines you've sent in <channel>
        without being interrupted by someone else (i.e. how long your current
        'monologue' is).  <channel> is only necessary if the message isn't sent
        in the channel itself.
        """
        i = 0
        for m in reversed(irc.state.history):
            if m.command != 'PRIVMSG':
                continue
            if not m.prefix:
                continue
            if not ircutils.strEqual(m.args[0], channel):
                continue
            if msg.prefix == m.prefix:
                i += 1
            else:
                break
        irc.reply(format('Your current monologue is at least %n long.',
                         (i, 'line')))
    monologue = wrap(monologue, ['channel'])

Class = Games


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
