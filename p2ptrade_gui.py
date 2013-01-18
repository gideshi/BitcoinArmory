from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qtdefines import *

from armoryengine import *

import qtdialogs

import p2ptrade

class OfferDispModel(QAbstractTableModel):
    def __init__(self, side):
        super(OfferDispModel, self).__init__()
        self.offers = []
        self.side = side

    def rowCount(self, index):  return len(self.offers)
    def columnCount(self, index): return 2

    def data(self, index, role=Qt.DisplayRole):
        row, col = index.row(), index.column()
        offer = self.offers[row]

        if self.side == 'B':
            # bid
            quantity = offer.B['value']
            total = offer.A['value']
        else:
            # ask
            quantity = offer.A['value']
            total = offer.B['value']

        price = float(total)/quantity
        price = coin2str(price)

        if role==Qt.DisplayRole:
            val = (quantity,  price)[col]
            return QVariant(val)
        elif role==Qt.ForegroundRole:
            if isinstance(offer, p2ptrade.MyExchangeOffer):
                return QVariant(Colors.TextGreen)
        elif role==Qt.BackgroundColorRole:
            if isinstance(offer, p2ptrade.MyExchangeOffer):
                return QVariant(Colors.SlightBlue)
            
        return QVariant()

    def headerData(self, section, orientation, role):
        colLabels = ['Quantity', 'Price']
        if role==Qt.DisplayRole:
            if orientation==Qt.Horizontal:
                return QVariant( colLabels[section])
        return QVariant()


class P2PTradeDialog(qtdialogs.ArmoryDialog):

    class Side:
        def __init__(self, side, parent):
            self.side = side
            self.parent = parent

        def updateOffers(self, offers):
            self.offersModel.offers = offers
            self.offersModel.reset()

        def dblClickOffer(self, index):
            offer = self.offersModel.offers[index.row()]
            if isinstance(offer, p2ptrade.MyExchangeOffer):
                reply = QMessageBox.information(self.parent, "Cancel order",
                                                "Should we cancel selected order?", QMessageBox.Yes | QMessageBox.No)
                if reply==QMessageBox.Yes:
                    self.parent.agent.cancelMyOffer(offer)
            else:
                if self.parent.agent.hasActiveEP():
                    # TODO: offer delayed fill
                    return QMessageBox.warning(self.parent, "Cannot fill an offer",
                                               "Exchange agent is currently busy with a trade, cannot fill an offer now",
                                               QMessageBox.Ok)

                # we need to sell to fill a bid
                buy_or_sell = ["buy", "sell"][self.side == 'B']

                btc_total, cc_total, price, side = self.parent.getOfferInfo(offer, fmt=True)

                msg = "You are about to %s %s %s at price %s per unit. Total cost: %s BTC. Proceed?" \
                    % (buy_or_sell, cc_total, self.parent.color_name, price, btc_total)
                reply = QMessageBox.information(self.parent, "Fill an offer",
                                                msg, QMessageBox.Ok | QMessageBox.Cancel)
                if reply==QMessageBox.Ok:
                    self.parent.agent.makeExchangeProposal(offer, None, offer.B['value'], None)

        def clickOrderButton(self):
            quantity = float(str(self.quantityEdit.text()).strip())
            price = float(str(self.priceEdit.text()).strip())
            btc_total = int(ONE_BTC * price * quantity)
            colored_total = int(quantity * self.parent.color_unit)

            colored_side = {"value": colored_total, "colorid": self.parent.select_colorid}
            btc_side = {"value": btc_total, "colorid": ''}
            if self.side == 'B':
                a, b = btc_side, colored_side
            else:
                a, b = colored_side, btc_side
            offer = p2ptrade.MyExchangeOffer(None, a, b, auto_post=True)
            self.parent.submitOffer(offer)


    def init_view(self):
        
        def mkside(side, top = 1):
            if side.side == 'A':
                left = 2
            else:
                left = 0
            orderbox = QFrame()
            orderbox.setFrameStyle(QFrame.Box|QFrame.Sunken)
            self.layout.addWidget(orderbox, top + 0, left+0)
            olayout = QFormLayout()
            orderbox.setLayout(olayout)

            buy_or_sell = ["Buy", "Sell"][side.side == 'A']

            olayout.addRow(QLabel("<b>%s %s</b>" % (buy_or_sell, self.color_name)))

            side.quantityEdit = QLineEdit()
            olayout.addRow("Quantity  <small>(units)</small>", side.quantityEdit)
            side.priceEdit = QLineEdit()
            olayout.addRow("Price <small>(BTC/unit)</small>", side.priceEdit)
            olayout.addRow(QLabel("Total BTC:"))
            
            orderBtn = QPushButton(["Buy", "Sell"][side.side != 'B'])
            olayout.addRow(orderBtn)
            self.connect(orderBtn, SIGNAL('clicked()'), side.clickOrderButton)

            side.offersView = QTableView()
            side.offersModel = OfferDispModel(side.side)
            side.offersView.setModel(side.offersModel)
            side.offersView.setSelectionBehavior(QTableView.SelectRows)
            side.offersView.setSelectionMode(QTableView.SingleSelection)
            side.offersView.horizontalHeader().setStretchLastSection(True)
            side.offersView.verticalHeader().setDefaultSectionSize(20)
            self.connect(side.offersView, SIGNAL('doubleClicked(QModelIndex)'),
                         side.dblClickOffer)
            self.layout.addWidget(QLabel("<b>%s</b" % ['Bids:', 'Asks:'][side.side != 'B']), top+1, left+0)
            self.layout.addWidget(side.offersView, top+2, left+0)

        self.bid_side = self.Side('B', self)
        mkside(self.bid_side)
        self.ask_side = self.Side('A', self)
        mkside(self.ask_side)


    def __init__(self, wlt, parent, main):
        super(P2PTradeDialog, self).__init__(parent, main)
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.wlt = wlt

        color = self.wlt.color
        self.color = color
        if color >= 0:
            self.select_colorid = color_definitions[color][1]['colorid']
            self.color_name = color_definitions[color][0]
            self.color_unit = int(color_definitions[color][1].get('unit', 1))
        else:
            self.select_colorid = ''
            self.color_name = "BTC"
            self.color_unit = ONE_BTC

        conbox = QFrame()
        conbox.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        conbox.setFrameStyle(QFrame.Box|QFrame.Sunken)
        self.layout.addWidget(conbox, 0, 0, 1, 3)
        self.con_layout = QGridLayout()
        conbox.setLayout(self.con_layout)

        self.connectBtn = QPushButton('Connect')
        self.con_layout.addWidget(self.connectBtn, 0, 0)
        self.connect(self.connectBtn, SIGNAL('clicked()'), self.connectP2P)

        self.urlEdit = QLineEdit()
        self.urlEdit.setText('http://srv7.coventry.fennec.name:8090/messages')
        self.con_layout.addWidget(self.urlEdit, 0, 1, 1, 3)
        
        self.connStat = QLabel('')
        self.con_layout.addWidget(self.connStat, 1, 0, 1, 2)

        sidebox = QWidget()
        self.layout.addWidget(sidebox, 0, 3, 4, 1)
        sblayout = QVBoxLayout()
        sidebox.setLayout(sblayout)
        

        # balance box
        bbox = QFrame()
        bbox.setFrameStyle(QFrame.Box|QFrame.Sunken)
        bbox.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sblayout.addWidget(bbox)
        blayout = QGridLayout()
        bbox.setLayout(blayout)
        blayout.addWidget(QLabel("<b>Balance</b> (w/unconfirmed)"), 0, 0, 1, 2)
        blayout.addWidget(QLabel("Bitcoin:"), 1, 0)
        self.btcBalance = QLabel("-")
        blayout.addWidget(self.btcBalance, 1, 1)
        blayout.addWidget(QLabel("%s:" % self.color_name), 2, 0)
        self.ccBalance = QLabel("-")
        blayout.addWidget(self.ccBalance, 2, 1)
        self.updateBalance()

        sblayout.addWidget(QLabel("<b>My trades:</b>"))

        # trade log
        tlview = QTableView()
        tlview.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sblayout.addWidget(tlview)
        self.tlitems = QStandardItemModel(0, 3)
        tlview.setModel(self.tlitems)
        tlview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tlview.horizontalHeader().setStretchLastSection(True)
        tlview.verticalHeader().setDefaultSectionSize(20)
        self.tlitems.setHorizontalHeaderLabels(["T", "Quantity", "Price"])
        for i in xrange(3):
            tlview.resizeColumnToContents(i)

        # trade in progress box
        tipbox = QFrame()
        tipbox.hide()
        self.tipbox = tipbox
        tipbox.setFrameStyle(QFrame.Box|QFrame.Sunken)
        #tipbox.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)
        sblayout.addWidget(tipbox)
        tiplayout = QGridLayout()
        tipbox.setLayout(tiplayout)
        tiplayout.addWidget(QLabel("<b>Trade in progress</b>"), 0, 0, 1, 2)
        tiplayout.addWidget(QLabel("State:"), 1, 0)
        self.tipState = QLabel('')
        tiplayout.addWidget(self.tipState, 1, 1)
        self.tipBuyOrSell = QLabel('')
        tiplayout.addWidget(self.tipBuyOrSell, 2, 0)
        tiplayout.addWidget(QLabel("%s:" % self.color_name), 3, 0)
        self.tipCCAmount = QLabel('')
        tiplayout.addWidget(self.tipCCAmount, 3, 1)

        tiplayout.addWidget(QLabel("Bitcoin:"), 4, 0)
        self.tipBtcAmount = QLabel('')
        tiplayout.addWidget(self.tipBtcAmount, 4, 1)

        tiplayout.addWidget(QLabel("Price:"), 5, 0)
        self.tipPrice = QLabel('')
        tiplayout.addWidget(self.tipPrice, 5, 1)

        tiplayout.addWidget(QLabel("Time left:"), 6, 0)
        self.tipTimeLeft = QLabel('')
        tiplayout.addWidget(self.tipTimeLeft, 6, 1)


        # blank stretch items to avoid stretching of info boxes
        sblayout.addStretch(1)
        self.layout.setRowStretch(3, 1)

        self.setMinimumSize(800, 600)

        self.layout.setColumnMinimumWidth(1, 10) # spacer

        self.setWindowTitle("P2P Trade: %s <-> BTC" % self.color_name)
        self.agent = None

    def updateBalance(self):
        self.btcBalance.setText(coin2str(self.wlt.getBalanceX(-1, "Total")))
        self.ccBalance.setText(coin2strX(self.color,
                                         self.wlt.getBalanceX(self.color, "Total")))

    def updateTIP(self):
        if self.agent and self.agent.hasActiveEP():
            ep = self.agent.active_ep
            self.tipState.setText(ep.state)
            total_btc, total_cc, price, cc_side = self.getOfferInfo(ep.offer, fmt=True)

            my_side = ['A', 'B'][ep.state == 'proposed']
            # if our side is colored then we are selling
            action = ['We buy', 'We sell'][my_side == cc_side]

            self.tipBuyOrSell.setText(action)
            self.tipCCAmount.setText(total_cc)
            self.tipBtcAmount.setText(total_btc)
            self.tipPrice.setText(price)
            self.tipTimeLeft.setText("%s sec." % int(self.agent.ep_timeout - time.time()))
            self.tipbox.show()
        else:
            self.tipbox.hide()

    def update(self):
        try:
            if not self.agent:
                return
            if self.comm.safeUpdate():
                connstate = 'active'
                self.showOrderBook()
            else:
                connstate = '<b>defunct</b>'
                self.connStat.setText("Connection: %s" % connstate)
                self.updateBalance()
                self.updateTIP()
        except Exception as e:
            LOGERROR("Unexpected error in P2P Dialog update: ", e)

    def submitOffer(self, offer):
        self.agent.registerMyOffer(offer)
        self.update()

    def showOrderBook(self):
        asks = []
        bids = []

        all_offers = self.agent.their_offers.values() + self.agent.my_offers.values()
        for offer in all_offers:
            if offer.A['colorid'] == self.select_colorid:
                asks.append(offer)
            elif offer.B['colorid'] == self.select_colorid:
                bids.append(offer)

        self.bid_side.updateOffers(bids)
        self.ask_side.updateOffers(asks)

    def cleanup(self):
        if self.update in self.main.extraHeartbeatFunctions:
            self.main.extraHeartbeatFunctions.remove(self.update)

    def closeEvent(self, event):
        self.cleanup()
        return super(P2PTradeDialog, self).closeEvent(event)

    def getOfferInfo(self, offer, fmt=False):
        if offer.A['colorid'] == '':
            colored, uncolored = offer.B, offer.A
            side = 'B'
        elif offer.B['colorid'] == '':
            colored, uncolored = offer.A, offer.B
            side = 'A'
        else:
            raise Exception, "both sides are of offer are colored"

        if colored['colorid'] != self.select_colorid:
            raise Exception, "offer is of wrong color"
        
        total_btc = uncolored['value']
        total_cc = float(colored['value'])/self.color_unit
        btc_per_unit = total_btc/total_cc

        if fmt:
            total_btc = coin2str(total_btc)
            total_cc = coin2strX(self.color, colored['value'])
            btc_per_unit = coin2str(btc_per_unit)

        return (total_btc, total_cc, btc_per_unit, side)

    def notifyCompleteTrade(self, ep):
        total_btc, total_cc, price, colored_side = self.getOfferInfo(ep.offer, fmt=True)
        
        my_side = ['A', 'B'][ep.state == 'proposed']
        action = ['bought', 'sold'][my_side == colored_side]
        saction = ['B', 'S'][my_side == colored_side]

        t = time.localtime()
        date = time.strftime('%Y-%m-%d %H:%M:%S', t)

        # if our side is colored then we are selling
        tooltip = "%s: You %s %s of %s at price %s per unit (%s BTC total)." \
            % (date, action, total_cc, self.color_name, price, total_btc)

        items = []

        for s in [saction, total_cc, price]:
            item = QStandardItem(s)
            item.setToolTip(tooltip)
            items.append(item)

        self.tlitems.appendRow(items)

    def connectP2P(self):
        url = str(self.urlEdit.text()).strip()
        self.comm = p2ptrade.HTTPExchangeComm(url)
        self.agent = p2ptrade.ExchangePeerAgent(self.wlt, self.comm)
        self.agent.onCompleteTrade.append(self.notifyCompleteTrade)
        self.comm.addAgent(self.agent)
        self.comm.update()
        self.connectBtn.setEnabled(False)
        self.connectBtn.setText("Connected")
        self.urlEdit.setReadOnly(True)
        self.init_view()
        self.update()
        self.main.extraHeartbeatFunctions.append(self.update)

