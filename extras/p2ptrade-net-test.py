import sys
sys.path.append('..')
sys.path.append('.')

from armoryengine import *
import connector

import p2ptrade
import colortools

import time

connector.init()

try:
    import p2ptrade_test_config
    testcolor = p2ptrade_test_config.testcolor
    msg_url = p2ptrade_test_config.msg_url
except:
    testcolor = '8ec9668e393f2b7682daa2fd40eeee873c07c9ed'
    msg_url = 'http://localhost:8080/messages'

comms = []

def mkagent(wfile):
    wlt = PyBtcWallet().readWalletFile(wfile)
    connector.register_wallet(wlt)
    c = p2ptrade.HTTPExchangeComm(msg_url)
    comms.append(c)
    a = p2ptrade.ExchangePeerAgent(wlt, c)
    c.addAgent(a)
    # c.startUpdateLoopThread(2)
    return a

ag1 = mkagent(CLI_ARGS[0])
ag2 = mkagent(CLI_ARGS[1])


uncolored = ''

o1 = p2ptrade.MyExchangeOffer(None, {"value": 100, "colorid": testcolor}, {'value': 100, 'colorid': uncolored})
o2 = p2ptrade.MyExchangeOffer(None, {"value": 100, "colorid": uncolored}, {"value": 100, 'colorid': testcolor}, False)

# get_main().do_not_broadcast = True

ag1.registerMyOffer(o1)
print "o1 registered"
ag2.registerMyOffer(o2)
print "o2 registered"

from twisted.internet import reactor

def update_loop():
    for c in comms:
        c.safeUpdate()
    reactor.callLater(5, update_loop)

reactor.callLater(5, update_loop)
connector.run()

