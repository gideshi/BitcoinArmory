from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qtdefines import *

from armoryengine import *

import qtdialogs

import p2ptrade

class P2PTradeDialog(qtdialogs.ArmoryDialog):
    def __init__(self, wlt, parent=None, main=None):
        super(P2PTradeDialog, self).__init__(parent, main)
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.setWindowTitle("P2P Trade")
        self.wlt = wlt

        self.connectBtn = QPushButton('Connect')
        self.layout.addWidget(self.connectBtn, 0, 0)
        self.connect(self.connectBtn, SIGNAL('clicked()'), self.connectP2P)
        
        color = self.wlt.color
        if color >= 0:
            self.select_colorid = color_definitions[color][1]['colorid']
        else:
            self.select_colorid = ''

        self.agent = None

    def showOrderBook(self):
        if not self.agent:
            return

        asks = []
        bids = []

        for offer in self.agent.their_offers:
            if offer.A['colorid'] == self.select_colorid:
                asks.append(offer)
            elif offer.B['colorid'] == self.select_colorid:
                bids.append(offer)

        print "bids: %s" % bids
        print "asks: %s" % asks

    def connectP2P(self):
        self.comm = p2ptrade.HTTPExchangeComm('http://localhost:8090/messages')
        self.agent = p2ptrade.ExchangePeerAgent(self.wlt, self.comm)
        self.comm.addAgent(self.agent)
        self.comm.update()
        self.connectBtn.setEnabled(False)
        self.showOrderBook()
