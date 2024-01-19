"""This module handles the transaction zdkd_list_sbs_aftale."""

from itk_dev_shared_components.sap import gridview_util


def search_fp_list(session):
    """Search a list of all FP aftaler and copy the forretningspartnere to the clipboard.

    Args:
        session: The SAP session object.
    """
    # Open transaction
    session.findById("wnd[0]/tbar[0]/okcd").text = "zdkd_list_sbs_aftale"
    session.findById("wnd[0]").sendVKey(0)

    # Set filters
    session.findById("wnd[0]/usr/ctxt%%DYN004-LOW").text = "FP"
    session.findById("wnd[0]/usr/ctxt%%DYN005-LOW").text = "01"
    session.findById("wnd[0]/usr/txt%%DYN011-LOW").text = ""

    # Set "Oprettet af" filter
    session.findById("wnd[0]/usr/btn%_%%DYN006_%_APP_%-VALU_PUSH").press()
    session.findById("wnd[1]/usr/tabsTAB_STRIP/tabpNOSV").select()
    session.findById("wnd[1]/usr/tabsTAB_STRIP/tabpNOSV/ssubSCREEN_HEADER:SAPLALDB:3030/tblSAPLALDBSINGLE_E/txtRSCSEL_255-SLOW_E[1,0]").text = "ZDKD_WS1_751"
    session.findById("wnd[1]/tbar[0]/btn[8]").press()

    # Search
    session.findById("wnd[0]/tbar[1]/btn[8]").press()

    # Scroll table to load all rows
    table = session.findById("wnd[0]/usr/cntlCONTAINER_AGREEMENT_EFI/shellcont/shell")
    gridview_util.scroll_entire_table(table)

    # Copy Forretningspartner column to clipboard
    table.selectColumn("PARTNER")
    table.contextMenu()
    table.selectContextMenuItemByText("Kopier tekst")

    # Exit to home screen
    session.findById("wnd[0]/tbar[0]/btn[12]").press()
    session.findById("wnd[0]/tbar[0]/btn[12]").press()
