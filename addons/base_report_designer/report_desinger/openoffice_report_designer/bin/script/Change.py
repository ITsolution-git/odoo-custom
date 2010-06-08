if __name__<>"package":
    from lib.gui import *
    from lib.functions import *
    from lib.rpc import *

class Change:
    def __init__(self, aVal= None, sURL=""):
        self.win=DBModalDialog(60, 50, 120, 90, "Connect to Open ERP Server")

        self.win.addFixedText("lblVariable", 38, 12, 60, 15, "Server")

        self.win.addEdit("txtHost",-2,9,60,15,sURL[sURL.find("/")+2:sURL.rfind(":")])

        self.win.addFixedText("lblReportName",45 , 31, 60, 15, "Port")
        self.win.addEdit("txtPort",-2,28,60,15,sURL[sURL.rfind(":")+1:])

        self.win.addFixedText("lblLoginName", 2, 51, 60, 15, "Protocol Connection")

        self.win.addComboListBox("lstProtocol", -2, 48, 60, 15, True)
        self.lstProtocol = self.win.getControl( "lstProtocol" )

#        self.lstProtocol.addItem( "XML-RPC", 0)
        #self.lstProtocol.addItem( "XML-RPC secure", 1)
        #self.lstProtocol.addItem( "NET-RPC (faster)", 2)

        self.win.addButton( 'btnOK', -2, -5, 30, 15, 'Ok', actionListenerProc = self.btnOk_clicked )

        self.win.addButton( 'btnCancel', -2 - 30 - 5 ,-5, 30, 15, 'Cancel', actionListenerProc = self.btnCancel_clicked )
        self.aVal=aVal
        self.protocol = {
            'XML-RPC': 'http://',
            'XML-RPC secure': 'https://',
            'NET-RPC': 'socket://',
        }
        for i in self.protocol.keys():
            self.lstProtocol.addItem(i,self.lstProtocol.getItemCount() )

        sValue=self.protocol.keys()[0]
        if sURL<>"":
            sValue=self.protocol.keys()[self.protocol.values().index(sURL[:sURL.find("/")+2])]

        self.win.doModalDialog( "lstProtocol", sValue)

    def btnOk_clicked(self,oActionEvent):
        global url
        url = self.protocol[self.win.getListBoxSelectedItem("lstProtocol")]+self.win.getEditText("txtHost")+":"+self.win.getEditText("txtPort")
        self.sock=RPCSession(url)
        docinfo=doc.getDocumentInfo()        
        docinfo.setUserFieldValue(0,url)
        res=self.sock.listdb()
        if res == -1:
            self.aVal.append(url)
        elif res == 0:
            self.aVal.append("No Database found !!!")
        else:
            self.aVal.append(url)
        self.aVal.append(res)
        self.win.endExecute()

    def btnCancel_clicked( self, oActionEvent ):
        self.win.endExecute()

