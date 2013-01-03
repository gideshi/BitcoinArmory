import sys
sys.path.append('..')
sys.path.append('.')

from armoryengine import *
import connector

import p2ptrade
import colortools

connector.init()

class EchoExchangeComm:
    def __init__(self):
        self.agents = []
    def addAgent(self, agent):
        self.agents.append(agent)
    def postMessage(self, content):
        print content
        for a in self.agents:
            a.dispatchMessage(content)

comm = EchoExchangeComm()

def mkagent(wfile):
    wlt = PyBtcWallet().readWalletFile(wfile)
    connector.register_wallet(wlt)
    a = p2ptrade.ExchangePeerAgent(wlt, comm)
    comm.addAgent(a)
    return a

ag1 = mkagent(CLI_ARGS[0])
ag2 = mkagent(CLI_ARGS[1])

testcolor = '26546d600e1a6a278eba2170559afe415ddcdd88'
uncolored = ''

o1 = p2ptrade.MyExchangeOffer(None, {"value": 100, "colorid": testcolor}, {'value': 100, 'colorid': uncolored})
o2 = p2ptrade.MyExchangeOffer(None, {"value": 100, "colorid": uncolored}, {"value": 100, 'colorid': testcolor})

ag1.registerMyOffer(o1)
ag2.registerMyOffer(o2)

get_main().do_not_broadcast = True

print "      1      "
ag1.updateState()
print "      2      "
ag2.updateState()

print "      1.1      "
ag1.updateState()
print "      2.1      "
ag2.updateState()

