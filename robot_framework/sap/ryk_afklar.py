"""This module handles all actions regarding the zdkd_ryk_afklar transaction."""

from datetime import datetime

from itk_dev_shared_components.sap import gridview_util
from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueStatus

from robot_framework import config


def search_work_list(session) -> int:
    """Search out the work list in zdkd_ryk_afklar.
    This function assumes the clipboard contains forretningspartnere to filter on.

    Args:
        session: The SAP session object.

    Returns:
        The number of cases to handle.
    """
    # Open transaction
    session.findById("wnd[0]/tbar[0]/okcd").text = "zdkd_ryk_afklar"
    session.findById("wnd[0]").sendVKey(0)

    # Insert forretningspartnere from clipboard
    session.findById("wnd[0]/usr/btn%_%%DYN002_%_APP_%-VALU_PUSH").press()
    session.findById("wnd[1]/tbar[0]/btn[24]").press()
    session.findById("wnd[1]/tbar[0]/btn[8]").press()

    # Delete "Maks antal træffere"
    session.findById("wnd[0]/usr/txt%%DYN012-LOW").text = ""

    # Search
    session.findById("wnd[0]/tbar[1]/btn[8]").press()

    # Apply layout
    session.findById("wnd[0]/tbar[1]/btn[33]").press()
    layout_table = session.findById("wnd[1]/usr/ssubD0500_SUBSCREEN:SAPLSLVC_DIALOG:0501/cntlG51_CONTAINER/shellcont/shell")
    layout_index = gridview_util.find_row_index_by_value(layout_table, "TEXT", "RPA layout til håndtering af ryk_afklar")
    layout_table.setCurrentCell(layout_index, "TEXT")
    layout_table.clickCurrentCell()

    # Find number of cases
    case_table = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell")
    return case_table.rowCount


def handle_case(orchestrator_connection: OrchestratorConnection, session, row_index: int):
    """Open a case and try to add the bilag to an existing fp-aftale.

    Args:
        orchestrator_connection: The connection to OpenOrchestrator.
        session: The SAP session object.
        row_index: The row index of the case to handle in the work list.

    Raises:
        ValueError: If the bilag wasn't found in the forretningspartner's postliste.
    """
    case_table = session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell")

    # Scroll to row
    case_table.firstVisibleRow = row_index

    # Get the forretningspartner and bilagsnummer
    forretningspartner = case_table.getCellValue(row_index, "GPART")
    bilagsnummer = case_table.getCellValue(row_index, "OPBEL")

    reference = f"{forretningspartner}:{bilagsnummer}"
    if not check_queue(orchestrator_connection, reference):
        return

    queue_element = orchestrator_connection.create_queue_element(config.QUEUE_NAME, reference)
    orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.IN_PROGRESS)

    # Open forretningspartneroversigt
    case_table.selectedRows = row_index
    session.findById("wnd[0]/tbar[1]/btn[18]").press()
    session.findById("wnd[1]/usr/subSUB1:SAPLZDKD_DCL_CLARIFICATION:0100/btnBUTTON_FMCACOV").press()

    # Find the bilag in the postliste table and click "Vis relation"
    postliste_table = session.findById("wnd[0]/usr/tabsDATA_DISP/tabpDATA_DISP_FC1/ssubDATA_DISP_SCA:RFMCA_COV:0202/cntlRFMCA_COV_0100_CONT5/shellcont/shell")

    bilag_row = gridview_util.find_row_index_by_value(postliste_table, "OPBEL", bilagsnummer)

    if bilag_row == -1:
        raise ValueError("The bilagsnummer wasn't found.")

    postliste_table.setCurrentCell(bilag_row, "OPBEL")
    postliste_table.contextMenu()
    postliste_table.selectContextMenuItemByText("Vis relation")

    # Find the fp-aftale if any
    aftale_row = find_fp_aftale(postliste_table, bilagsnummer)

    # If a fp-aftale was found add the bilag to it
    if aftale_row != -1:
        aftale_added = add_bilag_to_aftale(session, aftale_row, bilagsnummer)
    else:
        aftale_added = False

    # Go back to the work list
    session.findById("wnd[0]/tbar[0]/btn[3]").press()

    if aftale_added:
        # Set status and save
        session.findById("wnd[1]/usr/subSUB_STATE:SAPLFKKCFC:0005/cmbCFC_INFO_DYNPSTRUCT-WORKSTATE").value = 'Manuelt afsluttet'
        session.findById("wnd[1]/tbar[0]/btn[7]").press()
        session.findById("wnd[2]/usr/btnSPOP-OPTION1").press()
        orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE, message="Bilag tilføjet til aftale.")
    else:
        # Cancel
        session.findById("wnd[1]/tbar[0]/btn[12]").press()
        orchestrator_connection.set_queue_element_status(queue_element.id, QueueStatus.DONE, message="Bilag ikke tilføjet til aftale.")

    # Unlock case
    session.findById("wnd[0]/usr/cntlGRID1/shellcont/shell").selectedRows = row_index
    session.findById("wnd[0]/tbar[1]/btn[20]").press()


def check_queue(orchestrator_connection: OrchestratorConnection, reference: str) -> bool:
    """Check if the case should be skipped either because it has been handled in the last week
    or if it has caused an error twice in the last week.

    Args:
        orchestrator_connection: The connection to OpenOrchestrator
        reference: The case reference.

    Returns:
        True if the case should be handled.
    """
    # Check if the case has been handled successfully in the last week
    queue_elements = orchestrator_connection.get_queue_elements(config.QUEUE_NAME, reference=reference, status=QueueStatus.DONE)

    for element in queue_elements:
        if (datetime.now() - element.created_date).days <= 7:
            orchestrator_connection.log_info("Skipping: Handled in the last week.")
            return False

    # Check if the case has failed more than once in the last week
    queue_elements = orchestrator_connection.get_queue_elements(config.QUEUE_NAME, reference=reference, status=QueueStatus.IN_PROGRESS)

    fail_count = 0
    for element in queue_elements:
        if (datetime.now() - element.created_date).days <= 7:
            fail_count += 1

    if fail_count > 1:
        orchestrator_connection.log_info("Skipping: Failed twice in the last week.")
        return False

    return True


def find_fp_aftale(postliste_table, bilagsnummer: str) -> int:
    """Check the postliste to see if there is a fp-aftale on the hovedstol.
    Also check if the bilag doesn't have a red 'Lyssignal'.

    Args:
        postliste_table: The postliste gridview object.
        bilagsnummer: The bilagsnummer to search on.

    Returns:
        The row index of the fp aftale if any else -1.
    """
    aftale_index = -1
    bilag_index = -1

    for row in range(postliste_table.rowCount):
        # Check if bilag is in list TODO: What?
        if postliste_table.getCellValue(row, "OPBEL") == bilagsnummer:
            bilag_index = row

            # Check bilag for red "Lyssignal"
            if postliste_table.getCellValue(row, "AMPEL") != r"@0A\QTilgodehavende åbent og forfaldent@":
                return -1

        # Check for fp-aftale on hovedstol (FK/FE)
        if postliste_table.getCellValue(row, "BLART") in ('FK', 'FE') and postliste_table.getCellValue(row, "ZZAGREEMENTTYPE") == 'FP':
            aftale_index = row

    # Do a safety check that the bilag was found. Ideally this should never happen.
    if bilag_index == -1:
        return -1

    return aftale_index


def add_bilag_to_aftale(session, aftale_row: int, bilagsnummer: str) -> bool:
    """Check if the bilag can be added and then add the bilag to the fp-aftale. 

    Args:
        session: The SAP session object.
        aftale_row: The row index of the fp-aftale in the postliste.
        bilagsnummer: The bilagsnummer to add.

    Returns:
        True if the bilag was added.
    """
    # Right click aftale cell and click 'Vis Aftale'
    postliste_table = session.findById("wnd[0]/usr/tabsDATA_DISP/tabpDATA_DISP_FC1/ssubDATA_DISP_SCA:RFMCA_COV:0202/cntlRFMCA_COV_0100_CONT5/shellcont/shell")
    postliste_table.setCurrentCell(aftale_row, "ZZAGREEMENTTYPE")
    postliste_table.contextMenu()
    postliste_table.selectContextMenuItemByText("Vis Aftale")

    # Check 'Oprettet af'
    if session.findById("wnd[0]/usr/subSUBSCREEN_AREA1:SAPLZDKD_AGR:0120/subSUBSCREEN_AREA1:SAPLZDKD_AGR:0125/txtLCL_SUB_0125=>CRUSR").text == 'ZDKD_WS1_751':
        # Cancel and go back
        session.findById("wnd[0]/tbar[0]/btn[3]").press()
        return False

    # Click Tilføj position
    session.findById("wnd[0]/usr/ssubSUBSCREEN_AREA2:SAPLZDKD_AGR:0400/tabsTABSTRIP_0400/tabpFKT_TAB_02/ssubSUBAREA_0400:SAPLZDKD_AGR:0462/btnBUTTON_ADD_ITEM").press()

    # Filter on bilagsnummer and activate
    session.findById("wnd[0]/usr/subINCL_1000:SAPLFKB4:2000/tblSAPLFKB4CTRL_2000/txtFKKCLIT-OPBEL[4,0]").setFocus()
    session.findById("wnd[0]/usr/subINCL_1000:SAPLFKB4:2000/btnPUSH_SU").press()
    session.findById("wnd[1]/usr/txtRFKB4-SEL01").text = bilagsnummer
    session.findById("wnd[1]/usr/txtRFKB4-SEL02").text = bilagsnummer
    session.findById("wnd[1]/tbar[0]/btn[0]").press()
    session.findById("wnd[0]/usr/subINCL_1000:SAPLFKB4:2000/btnPUSH_MF").press()
    session.findById("wnd[0]/usr/subINCL_1000:SAPLFKB4:2000/btnPUSH_PA").press()

    # Save and exit
    session.findById("wnd[0]/tbar[0]/btn[11]").press()
    session.findById("wnd[1]/tbar[0]/btn[0]").press()
    session.findById("wnd[0]/tbar[0]/btn[11]").press()
    session.findById("wnd[0]/tbar[0]/btn[3]").press()

    return True
