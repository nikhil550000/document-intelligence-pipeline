"""Parties pieces that the rules cannot read, with the names each one holds."""

# Each piece is written exactly as in CUAD's answer. Its names are copied from it
# and never corrected, so a misspelling such as `Corporatino` stays.
PARTIES_BY_HAND: dict[str, tuple[str, ...]] = {
    # The rules give one name per piece, and these pieces name several parties.
    (
        "VA Partners I, LLC, ValueAct Capital Master Fund, L.P., ValueAct Capital "
        "Management, L.P., ValueAct Capital Management, LLC, ValueAct Holdings, L.P. "
        "(collectively, the “ValueAct Group”, and individually a “member” of the "
        "ValueAct Group)"
    ): (
        "VA Partners I, LLC",
        "ValueAct Capital Master Fund, L.P.",
        "ValueAct Capital Management, L.P.",
        "ValueAct Capital Management, LLC",
        "ValueAct Holdings, L.P.",
    ),
    (
        "American United Life Insurance Company and OneAmerica Securities, Inc. "
        '(collectively referred to as "Servicing Agent", "you", or "your")'
    ): ("American United Life Insurance Company", "OneAmerica Securities, Inc."),
    "Bank of America Corporatino, Banc of America Preferred Funding Corporation": (
        "Bank of America Corporatino",
        "Banc of America Preferred Funding Corporation",
    ),
    'Food For Athletes, Inc./Gridiron BioNutrients™ (collectively the "Company")': (
        "Food For Athletes, Inc.",
        "Gridiron BioNutrients™",
    ),
    (
        "Food For Athletes, Inc./ Gridiron Gridiron BioNutrients™ (collectively, the "
        '"Company")'
    ): ("Food For Athletes, Inc.", "Gridiron Gridiron BioNutrients™"),
    (
        "MINDA INDUSTRIES LIMITED including its successors and permitted assigns "
        '("MIL"), Nirmal K. MINDA including his heirs, executors, administrators or '
        'successors and permitted assigns ("MINDA")'
    ): ("MINDA INDUSTRIES LIMITED", "Nirmal K. MINDA"),
    'WYZZ, Inc. and WYZZ Licensee, Inc. (collectively "WYZZ")': (
        "WYZZ, Inc.",
        "WYZZ Licensee, Inc.",
    ),
    (
        "Kes 7 Capital Inc. and Bloom Burton & Co. Ltd. (collectively with the Lead "
        'Agent, "Agents" and each individually an "Agent")'
    ): ("Kes 7 Capital Inc.", "Bloom Burton & Co. Ltd."),
    "K*TEC OPERATING CORP., SUNCTRON GCO L.P.": (
        "K*TEC OPERATING CORP.",
        "SUNCTRON GCO L.P.",
    ),
    (
        'Zebra Technologies International, LLC ("Zebra"), Zebra Technologies do Brasil '
        '- Comércio de Produtos de Informåtica Ltda.("Zebra Brazil"), Xplore '
        'Technologies Corporation of America ("Xplore"), (Zebra, Zebra Brazil and '
        'Explore collectively as "Zebra")'
    ): (
        "Zebra Technologies International, LLC",
        "Zebra Technologies do Brasil - Comércio de Produtos de Informåtica Ltda.",
        "Xplore Technologies Corporation of America",
    ),
    (
        'ScanSource, Inc. ("ScanSource"), ScanSource Latin America, Inc. ("ScanSource '
        'Latin America"), ScanSource Brazil Distribuidora de Technologias, Ltda. '
        '"ScanSource Brazil"), SCANSOURCE DE MEXICO S. DE R.L. DE C.V. ("ScanSource '
        'Mexico") ,("ScanSource", "ScanSource Latin America" , "ScanSource Brazil" and '
        'ScanSource Mexico collectively "Distributor")("Zebra" and the "Distributor" '
        'are referred to collectively as \'Parties" and individually as a "Party")'
    ): (
        "ScanSource, Inc.",
        "ScanSource Latin America, Inc.",
        "ScanSource Brazil Distribuidora de Technologias, Ltda.",
        "SCANSOURCE DE MEXICO S. DE R.L. DE C.V.",
    ),
    'Mr. Zheng Qing, Mr. Gu Xianwin and Ms. Chen Weijie ("Developer")': (
        "Mr. Zheng Qing",
        "Mr. Gu Xianwin",
        "Ms. Chen Weijie",
    ),
    # The text in front of the alias holds words that are not part of the name,
    # such as "and its Affiliates", a former name or a place.
    (
        "General Electric Capital Corporation together with its successors and "
        "assigns, if any (“Lessor”)"
    ): ("General Electric Capital Corporation",),
    (
        "Mellon Investor Services LLC operating with the service name BNY Mellon "
        'Shareowner Services ("Agent")'
    ): ("Mellon Investor Services LLC",),
    (
        "The Bon-Ton Stores, Inc. and its associated chapter 11 debtors inpossession "
        "(collectively, “Merchant”)"
    ): ("The Bon-Ton Stores, Inc.",),
    'Parcelway Courier Systems Canada Ltd. a subsidiary of Dynamex Inc. ("Dynamex")': (
        "Parcelway Courier Systems Canada Ltd.",
    ),
    'Glu Mobile, Inc. f/k/a Sorrent, Inc. ("Licensee")': ("Glu Mobile, Inc.",),
    (
        "Constellation NewEnergy, Inc., on behalf of itself and its retail affiliates "
        "and subsidiaries (collectively, “Constellation”)"
    ): ("Constellation NewEnergy, Inc.",),
    (
        "IMPCO Technologies Inc. including its successors and permitted assigns "
        '("IMPCO")'
    ): ("IMPCO Technologies Inc.",),
    'The Integrity Funds, Integrity Funds Distributor, LLC, ("Integrity")': (
        "Integrity Funds Distributor, LLC",
    ),
    (
        'f/s/o Dwayne Wade ("Athlete" and together with Wade Enterprises '
        '(collectively, "Wade")'
    ): ("Dwayne Wade",),
    (
        "MERCK SERONO SA COINSINS, SWITZERLAND, AN AFFILIATE OF MERCK KGAA, DARMSTADT, "
        "GERMANY"
    ): ("MERCK SERONO SA",),
    "MERCK KGAA DARMSTADT, GERMANY": ("MERCK KGAA",),
    'AB Wately, Inc. and all of its subsidiaries and related companies ("ABW" )': (
        "AB Wately, Inc.",
    ),
    (
        "ABC Company and its duly licensed insurance affiliates indicated on the "
        "signature page of this   Agreement (collectively “Broker Dealer”, "
        "individually referred to as a “Party” and collectively with Issuer and "
        "Distributor as the “Parties”)"
    ): ("ABC Company",),
    # The end of a section title, cut apart at its semicolons.
    "Non-competition": (),
    "Non-solicitation]": (),
    'Sekisui Diagnostics, LLC and its Affiliates ("Sekisui")': (
        "Sekisui Diagnostics, LLC",
    ),
    'Qualigen, Inc. and its Affiliates ("Qualigen")': ("Qualigen, Inc.",),
    "Trust’s Advantus Money Market Fund (“Fund”)": ("Advantus Money Market Fund",),
    (
        "Cisco Systems, Inc. or its subsidiaries licensing the Software instead of "
        'Cisco Systems ("Cisco")'
    ): ("Cisco Systems, Inc.",),
    (
        'element 5 GmbH and its subsidiaries (together hereafter, "element 5") and who '
        "wish to make use of the additional service provided by element 5 (hereafter, "
        '"AffiliateManagement")'
    ): ("element 5 GmbH",),
    (
        "Vertical Enterprises LLC formerly known as Tradeum, Inc. which d/b/a "
        'VerticalNet Solutions ("VNE"'
    ): ("Vertical Enterprises LLC",),
    'Jaguar Investments, Inc. and its affiliates ("Power2Ship")': (
        "Jaguar Investments, Inc.",
    ),
    (
        "Wells Fargo Bank on behalf of Wells Fargo Mortgage Backed Securities 2006-6 "
        'Trust ("Counterparty")'
    ): ("Wells Fargo Bank",),
    'Glamis Gold Ltd. and all of its subsidiaries and other Affiliates ("Glamis")': (
        "Glamis Gold Ltd.",
    ),
    (
        "Western Copper Corporation and all of its subsidiaries and other Affiliates "
        '("Western Copper")'
    ): ("Western Copper Corporation",),
    # A bracket without a quotation mark is kept as part of the name, but these
    # hold a short or a former name.
    "Mutual Insurance Corporation of America (MICOA)": (
        "Mutual Insurance Corporation of America",
    ),
    'AHF Holding, Inc. (formerly known as Tarzan HoldCo, Inc.)("Buyer")': (
        "AHF Holding, Inc.",
    ),
    "Geno Auriemma (Auriemma)": ("Geno Auriemma",),
    'Berkshire Bank (Berkshire)("Party" or "Parties")': ("Berkshire Bank",),
    'deltathree.com, Inc. (formerly known as Delta Three, Inc.) ("DeltaThree")': (
        "deltathree.com, Inc.",
    ),
    'New China Media LLC ((a/k/a New China Media LLC) ("NCM")': (
        "New China Media LLC",
    ),
    # A role word or a description stands where the name should be.
    'sales agent (the "Agent" or "you")': (),
    'Agent ("Agent")': (),
    'Franchisee ("you")': (),
    'Supplier ("Supplier")': (),
    'You ("Affiliate")': (),
    'an individual ("Developer")': (),
    'Trust Advisors to the Seller Trusts ("Trust Advisors")': (),
    (
        'Franchisee ("you," "your" or "Franchisee") (We and you may collectively be '
        'referred to as the "Parties.")'
    ): (),
    "the seller": (),
    'Franchisee ("Franchisee")': (),
    "U.S. registered broker-dealer affiliate of the Agent": (),
    (
        'the individual or legal entity identified on the cover page ("Franchisee", '
        '"You", "your")'
    ): (),
    "Supplier": (),
    "Customer": (),
    'Web site owners (hereafter, "Affiliates")': (),
    "Software Publishers": (),
    'Distributor ("Distributor")': (),
    'Sagebrush partners ("Partners")': (),
    # These name the parties together. The drop rules miss them because of a slip
    # in an alias or its quotation marks, or because full names are used.
    'Gingko and BLI ("Party", collectively as the "Parties")': (),
    "CytoDyn and Vyera (“Party” and collectively as the “Parties.”)": (),
    (
        "HOFV and/or PFHOF, and Constellation, (“Party” and, collectively, as the "
        "“Parties”)"
    ): (),
    (
        "Wade Enterprises, Athlete and togetherwith Naked, (“Party” and collectively, "
        "the “Parties”)"
    ): (),
    'Phototronics and DNP ("Shareholder" and collectively as "Shareholders")': (),
    (
        "Skype, Online BVI, the Company, Skype Holding and Tom Holding (“party to this "
        "Agreement” and collectively as “parties to this Agreement.”)"
    ): (),
    'Oxbow and Global (individually as "Party" and collectively as the "Parties")': (),
    (
        "Subcontractor and Manufacturer (individually as “Party” or collectively as "
        'the “Parties")'
    ): (),
    (
        "TELCOSTAR PTE, LTD. and Ability Computer & Software Industries Ltd (each and "
        'both of them "Recipient")'
    ): (),
    (
        "AZUL LINHAS AÉREAS BRASILEIRAS and AVIONS DE TRANSPORT REGIONAL, G.I.E. "
        "(individually referred to as the “Party” or collectively as the “Parties”)"
    ): (),
    (
        "Marathon Petroleum Company LP and Marathon Pipe Line LLC (jointly as "
        '"Parties" and individually as a "Party")'
    ): (),
    (
        "AizuFujitsu Semiconductor Limited, Fujitsu Semiconductor Limited, Transphorm, "
        "Inc. (collectively referred to as the “Parties” and individually, a “Party”)"
    ): (),
}
