"""Find the PDF of each of CUAD's answer rows."""

from pathlib import Path

from docintel.evaluation.dataset import CUAD_FOLDER_NAME

PDF_FOLDER = Path("data") / CUAD_FOLDER_NAME / "CUAD_v1" / "full_contract_pdf"

# The 11 answer rows that do not give the file name of their PDF, each next to
# that file name. Every other row gives it exactly.
PDF_NAMES_THAT_DIFFER = {
    # The file name has _ where the answer file has & or '.
    "MACY'S,INC_05_11_2020-EX-99.4-JOINT FILING AGREEMENT.PDF": (
        "MACY_S,INC_05_11_2020-EX-99.4-JOINT FILING AGREEMENT.PDF"
    ),
    "MOELIS&CO_03_24_2014-EX-10.19-STRATEGIC ALLIANCE AGREEMENT.PDF": (
        "MOELIS_CO_03_24_2014-EX-10.19-STRATEGIC ALLIANCE AGREEMENT.PDF"
    ),
    "Monsanto Company - SECOND A&R EXCLUSIVE AGENCY AND MARKETING AGREEMENT .PDF": (
        "Monsanto Company - SECOND A_R EXCLUSIVE AGENCY AND MARKETING AGREEMENT .PDF"
    ),
    (
        "PACIRA PHARMACEUTICALS, INC. - A&R STRATEGIC LICENSING, DISTRIBUTION AND "
        "MARKETING AGREEMENT .PDF"
    ): (
        "PACIRA PHARMACEUTICALS, INC. - A_R STRATEGIC LICENSING, DISTRIBUTION AND "
        "MARKETING AGREEMENT .PDF"
    ),
    (
        "PLAYAHOTELS&RESORTSNV_03_14_2017-EX-10.22-STRATEGIC ALLIANCE AGREEMENT "
        "(Hyatt Ziva Cancun).PDF"
    ): (
        "PLAYAHOTELS_RESORTSNV_03_14_2017-EX-10.22-STRATEGIC ALLIANCE AGREEMENT "
        "(Hyatt Ziva Cancun).PDF"
    ),
    "Reinsurance Group of America, Incorporated - A&R REMARKETING  AGREEMENT.PDF": (
        "Reinsurance Group of America, Incorporated - A_R REMARKETING  AGREEMENT.PDF"
    ),
    "SightLife Surgical, Inc. - STRATEGIC SALES & MARKETING AGREEMENT.PDF": (
        "SightLife Surgical, Inc. - STRATEGIC SALES _ MARKETING AGREEMENT.PDF"
    ),
    # The answer file writes É as E followed by a separate accent mark.
    "LECLANCHÉ S.A. - JOINT DEVELOPMENT AND MARKETING AGREEMENT.PDF": (
        "LECLANCHÉ S.A. - JOINT DEVELOPMENT AND MARKETING AGREEMENT.PDF"
    ),
    # The file name ends in .pdf, not .PDF.
    (
        "FEDERATEDGOVERNMENTINCOMESECURITIESINC_04_28_2020-EX-99.SERV AGREE-SERVICES "
        "AGREEMENT.PDF"
    ): (
        "FEDERATEDGOVERNMENTINCOMESECURITIESINC_04_28_2020-EX-99.SERV AGREE-SERVICES "
        "AGREEMENT.pdf"
    ),
    # The answer file has a stray ' after the extension.
    "KALLOINC_11_03_2011-EX-10.1-STRATEGIC ALLIANCE AGREEMENT.PDF'": (
        "KALLOINC_11_03_2011-EX-10.1-STRATEGIC ALLIANCE AGREEMENT.PDF"
    ),
    # The file name has words the answer file does not, and ends in .pdf.
    (
        "HarpoonTherapeuticsInc_20200312_10-K_EX-10.18_12051356_EX-10.18_Development "
        "Agreement.PDF"
    ): (
        "HarpoonTherapeuticsInc_20200312_10-K_EX-10.18_12051356_EX-10.18_Development "
        "Agreement_Option Agreement.pdf"
    ),
}


def find_contract_pdfs(pdf_folder: Path, row_names: list[str]) -> dict[str, Path]:
    """Returns the PDF of each answer row, found anywhere under the folder.

    Raises:
        FileNotFoundError: A row's PDF is not in the folder, under the row's name
            or under the name the table gives it.
    """
    pdfs_by_file_name = {}
    for path in pdf_folder.rglob("*"):
        if path.is_file():
            pdfs_by_file_name[path.name] = path

    pdfs_by_row = {}
    for row_name in row_names:
        file_name = PDF_NAMES_THAT_DIFFER.get(row_name, row_name)
        if file_name not in pdfs_by_file_name:
            raise FileNotFoundError(
                f"No PDF in {pdf_folder} for the answer row {row_name!r}."
            )
        pdfs_by_row[row_name] = pdfs_by_file_name[file_name]
    return pdfs_by_row
