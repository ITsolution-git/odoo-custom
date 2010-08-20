 #!/usr/bin/python
 #-*- encoding: utf-8 -*-

from win32com import universal
from win32com.server.exception import COMException
from win32com.client import gencache, DispatchWithEvents
import winerror
import pythoncom
from win32com.client import constants
import sys
import os
from win32com.client import Dispatch
import win32con

sys.path.append(os.path.abspath(os.path.dirname(__file__)))    #outlook
sys.path.append(os.path.abspath(__file__))                     #outlook/addin

import manager
from win32com.client import CastTo
import win32ui
from tiny_xmlrpc import *

import locale
locale.setlocale(locale.LC_NUMERIC, "C")

# Support for COM objects we use.
gencache.EnsureModule('{00062FFF-0000-0000-C000-000000000046}', 0, 9, 0, bForDemand=True) # Outlook 9
gencache.EnsureModule('{2DF8D04C-5BFA-101B-BDE5-00AA0044DE52}', 0, 2, 1, bForDemand=True) # Office 9

# The TLB defiining the interfaces we implement
universal.RegisterInterfaces('{AC0714F2-3D04-11D1-AE7D-00A0C90F26F4}', 0, 1, 0, ["_IDTExtensibility2"])

global NewConn

# Retrieves registered XMLRPC connection
def GetConn():
    d=Dispatch("Python.OpenERP.XMLRpcConn")
    mngr = manager.GetManager()
    return d

class ButtonEvent:
    def OnClick(self, button, cancel):
        mngr = manager.GetManager()
        mngr.ShowManager()
        return cancel
#
class ViewPartners:
    def OnClick(self, button, cancel):
        from win32com.client import Dispatch
        import win32con
        mngr = manager.GetManager()
        data=mngr.LoadConfig()
        outlook = Dispatch("Outlook.Application")
        ex = outlook.ActiveExplorer()
        if ex:
            is_login = str(data['login'])
            if is_login == 'False':
                win32ui.MessageBox("Please login to the database first", "Database Connection", win32con.MB_ICONEXCLAMATION)
            elif ex.Selection.Count == 1 or ex.Selection.Count == 0:
                mngr = manager.GetManager()
                mngr.ShowManager("IDD_VIEW_PARTNER_DIALOG")
            elif ex.Selection.Count > 1:
                win32ui.MessageBox("Multiple selection not allowed. Please select only one mail at a time.","",win32con.MB_ICONINFORMATION)
        return cancel
#
class ArchiveEvent:
    def OnClick(self, button, cancel):
        from win32com.client import Dispatch
        import win32con
        mngr = manager.GetManager()
        data=mngr.LoadConfig()
        outlook = Dispatch("Outlook.Application")
        ex = outlook.ActiveExplorer()
        if ex:
            is_login = str(data['login'])
            if is_login == 'False':
                win32ui.MessageBox("Please login to the database first", "Database Connection", win32con.MB_ICONEXCLAMATION)
            elif ex.Selection.Count == 1:
                mngr = manager.GetManager()
                mngr.ShowManager("IDD_SYNC")
            elif ex.Selection.Count == 0:
                win32ui.MessageBox("No mail selected to archive to OpenERP","",win32con.MB_ICONINFORMATION)
            elif ex.Selection.Count > 1:
                win32ui.MessageBox("Multiple selection not allowed. Please select only one mail at a time.","",win32con.MB_ICONINFORMATION)
        return cancel
#
class OutlookAddin:
    _com_interfaces_ = ['_IDTExtensibility2']
    _public_methods_ = ['OnConnection','GetAppDataPath']
    _reg_clsctx_ = pythoncom.CLSCTX_INPROC_SERVER
    _reg_clsid_ = "{0F47D9F3-598B-4d24-B7E3-92AC15ED27E8}"
    _reg_progid_ = "Python.OpenERP.OutlookAddin"
    _reg_policy_spec_ = "win32com.server.policy.EventHandlerPolicy"
    def OnConnection(self, application, connectMode, addin, custom):
        # ActiveExplorer may be none when started without a UI (eg, WinCE synchronisation)
        activeExplorer = application.ActiveExplorer()
        if activeExplorer is not None:
            bars = activeExplorer.CommandBars

            menu_bar = bars.Item("Menu Bar")
            tools_menu = menu_bar.Controls(5)
            tools_menu = CastTo(tools_menu, "CommandBarPopup")

            item = tools_menu.Controls.Add(Type=constants.msoControlButton, Temporary=True)
            # Hook events for the item
            item = self.menu_bar_Button = DispatchWithEvents(item, ButtonEvent)
            item.Caption="OpenERP Configuration"
            item.TooltipText = "Click to configure OpenERP"
            item.Enabled = True

            item = tools_menu.Controls.Add(Type=constants.msoControlButton, Temporary=True)
            # Hook events for the item
            item = self.menu_bar_arch_Button = DispatchWithEvents(item, ArchiveEvent)
            item.Caption="Archive to OpenERP"
            item.TooltipText = "Click to archive to OpenERP"
            item.Enabled = True

            toolbar = bars.Item("Standard")

            item = toolbar.Controls.Add(Type=constants.msoControlButton, Temporary=True)
            # Hook events for the item
            item = self.toolbarButton = DispatchWithEvents(item, ArchiveEvent)
            item.Caption="Archive to OpenERP"
            item.TooltipText = "Click to archive to OpenERP"
            item.Enabled = True

            # Adding Menu in Menu Bar to the Web Menu of the Outlook
            toolbarweb = bars.Item("Web")
            # Hook events for the item
            item = toolbarweb.Controls.Add(Type = constants.msoControlButton, Temporary = True)
            item = self.toolbarButtonPartner = DispatchWithEvents(item, ViewPartners)
            item.Caption = "Open Contact"
            item.TooltipText = "Click to Open OpenERP Partner Contact Information."
            item.Enabled = True

            item = tools_menu.Controls.Add(Type=constants.msoControlButton, Temporary=True)
            # Hook events for the item
            item = self.menu_bar_viewpartner_Button = DispatchWithEvents(item, ViewPartners)
            item.Caption = "Open Contact"
            item.TooltipText = "Click to Open Partner detail"
            item.Enabled = True

    def OnDisconnection(self, mode, custom):
        mngr = manager.GetManager()
        mngr.config['login'] = False
        mngr.SaveConfig()
        print "OnDisconnection"
    def OnAddInsUpdate(self, custom):
        print "OnAddInsUpdate", custom
    def OnStartupComplete(self, custom):
        print "OnStartupComplete", custom
    def OnBeginShutdown(self, custom):
        print "OnBeginShutdown", custom
    def GetAppDataPath(self):
        mngr = manager.GetManager()
        return mngr.data_directory

def RegisterAddin(klass):
    import _winreg
    key = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Office\\Outlook\\Addins")
    subkey = _winreg.CreateKey(key, klass._reg_progid_)
    _winreg.SetValueEx(subkey, "CommandLineSafe", 0, _winreg.REG_DWORD, 0)
    _winreg.SetValueEx(subkey, "LoadBehavior", 0, _winreg.REG_DWORD, 3)
    _winreg.SetValueEx(subkey, "Description", 0, _winreg.REG_SZ, klass._reg_progid_)
    _winreg.SetValueEx(subkey, "FriendlyName", 0, _winreg.REG_SZ, klass._reg_progid_)

def UnregisterAddin(klass):
    import _winreg
    try:
        _winreg.DeleteKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Office\\Outlook\\Addins\\" + klass._reg_progid_)
    except WindowsError:
        pass

def UnregisterXMLConn(klass):
    import _winreg
    try:
        _winreg.DeleteKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Office\\Outlook\\Addins\\XMLConnection" + klass._reg_progid_)
    except WindowsError:
        pass

def RegisterXMLConn(klass):
    import _winreg
    key = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Office\\Outlook\\Addins\\XMLConnection")
    subkey = _winreg.CreateKey(key, klass._reg_progid_)
    _winreg.SetValueEx(subkey, "CommandLineSafe", 0, _winreg.REG_DWORD, 0)
    _winreg.SetValueEx(subkey, "LoadBehavior", 0, _winreg.REG_DWORD, 3)
    _winreg.SetValueEx(subkey, "Description", 0, _winreg.REG_SZ, klass._reg_progid_)
    _winreg.SetValueEx(subkey, "FriendlyName", 0, _winreg.REG_SZ, klass._reg_progid_)

if __name__ == '__main__':

    import win32com.server.register
    NewConn=XMLRpcConn()
    win32com.server.register.UseCommandLine(OutlookAddin)
    win32com.server.register.UseCommandLine(NewConn)
    if "--unregister" in sys.argv:
        UnregisterAddin(OutlookAddin)
        UnregisterXMLConn(NewConn)
    else:
        RegisterAddin(OutlookAddin)
        RegisterXMLConn(NewConn)

#mngr = manager.GetManager()
#mngr.ShowManager("IDD_MANAGER")
