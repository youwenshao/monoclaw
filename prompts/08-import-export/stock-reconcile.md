# StockReconcile

## Tool Name & Overview

StockReconcile automates the matching of shipping manifests with warehouse receipts to identify quantity discrepancies, missing items, and damaged goods. It handles both Full Container Load (FCL) and Less-than-Container Load (LCL) reconciliation workflows, tracks goods from port arrival through warehouse receipt to inventory posting. Built for the high-volume container throughput of Hong Kong's port logistics.

## Target User

Hong Kong warehouse operators, logistics coordinators, import-export companies, and freight forwarders who receive container shipments at Kwai Tsing Container Terminals or other HK port facilities and need to verify received quantities against shipping documents.

## Core Features

- **Document Ingestion**: Parses shipping manifests (bill of lading, packing lists), delivery orders, and warehouse receipts from PDF, Excel, and scanned document formats
- **Auto-Matching Engine**: Matches manifest line items against warehouse receipt entries by SKU, description, quantity, and container reference — highlights mismatches automatically
- **FCL/LCL Handling**: Supports both FCL (single consignee per container) and LCL (multiple consignees, deconsolidation required) reconciliation workflows
- **Discrepancy Management**: Creates discrepancy records for shortages, overages, and damage; generates claim documentation for carriers or insurers
- **Container Tracking**: Monitors container status from vessel arrival to terminal gate-out to warehouse delivery using reference numbers
- **Reconciliation Reports**: Produces summary and detail reports showing matched, unmatched, and discrepant items per shipment

## Tech Stack

- **Document Parsing**: PyPDF2, pdfplumber for PDF extraction; openpyxl for Excel parsing; Tesseract OCR for scanned documents
- **LLM**: MLX local inference for interpreting unstructured packing lists and matching ambiguous product descriptions
- **Matching**: rapidfuzz for fuzzy string matching of product descriptions; pandas for tabular data reconciliation
- **Database**: SQLite for shipments, manifest data, warehouse receipts, and discrepancy records
- **UI**: Streamlit dashboard with side-by-side manifest vs receipt comparison view
- **Export**: openpyxl for Excel reconciliation reports; reportlab for PDF claim documentation

## File Structure

```
~/OpenClaw/tools/stock-reconcile/
├── app.py                        # Streamlit reconciliation dashboard
├── ingestion/
│   ├── manifest_parser.py        # Shipping manifest / B/L parsing
│   ├── packing_list_parser.py    # Packing list extraction (PDF/Excel)
│   ├── warehouse_receipt_parser.py # Warehouse receipt parsing
│   └── ocr_handler.py            # Tesseract OCR for scanned documents
├── reconciliation/
│   ├── matching_engine.py        # Auto-match manifest to receipt
│   ├── fcl_reconciler.py         # FCL-specific reconciliation logic
│   ├── lcl_reconciler.py         # LCL deconsolidation and reconciliation
│   └── discrepancy_handler.py    # Discrepancy detection and categorization
├── tracking/
│   ├── container_tracker.py      # Container status monitoring
│   └── shipment_timeline.py      # Shipment lifecycle timeline
├── reports/
│   ├── reconciliation_report.py  # Match/mismatch summary reports
│   └── claim_generator.py        # Carrier/insurer claim documentation
├── models/
│   ├── llm_handler.py            # MLX inference wrapper
│   └── prompts.py                # Description matching prompts
├── data/
│   └── reconcile.db              # SQLite database
├── requirements.txt
└── README.md
```

## Key Integrations

- **Local LLM (MLX)**: Interprets ambiguous product descriptions and matches semantically similar items across documents
- **Tesseract OCR**: Processes scanned shipping documents that arrive as image PDFs
- **File System**: Watches a designated import folder for new shipping documents to process

## HK-Specific Requirements

- HKSAR Customs and Excise requirements: Import and export manifests must be retained for customs inspection; reconciliation records may be requested during audit
- Kwai Tsing Container Terminal logistics: The world's busiest container port handles 15M+ TEUs annually; tool must handle high-volume batch reconciliation
- Bonded warehouse procedures: Goods stored in bonded warehouses have additional documentation requirements — separate tracking for bonded vs non-bonded inventory
- Container types: Standard 20ft (TEU), 40ft (FEU), 40ft HC, and refrigerated containers — dimensions affect warehouse space allocation
- LCL deconsolidation: HK is a major transshipment hub; LCL cargo is deconsolidated at CFS (Container Freight Station) facilities — reconciliation must handle multiple consignees per container
- Bill of Lading types: Master B/L (shipping line) vs House B/L (forwarder) — tool must handle both and link them
- Common discrepancy causes in HK trade: Shortages due to partial loading at origin, damage during transshipment, quantity conversion errors (pieces vs cartons vs pallets)
- Free port status: No customs duties (except 4 dutiable categories) but goods must still be declared — reconciliation records support TDEC filing

## Data Model

```sql
CREATE TABLE shipments (
    id INTEGER PRIMARY KEY,
    shipment_reference TEXT UNIQUE,
    bl_number TEXT,
    bl_type TEXT CHECK(bl_type IN ('master','house')),
    master_bl TEXT,
    vessel_name TEXT,
    voyage TEXT,
    origin_port TEXT,
    arrival_date DATE,
    container_numbers TEXT,  -- JSON array
    load_type TEXT CHECK(load_type IN ('FCL','LCL')),
    consignee TEXT,
    status TEXT CHECK(status IN ('in_transit','arrived','gate_out','at_warehouse','reconciled','closed')) DEFAULT 'in_transit',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE manifest_items (
    id INTEGER PRIMARY KEY,
    shipment_id INTEGER REFERENCES shipments(id),
    container_number TEXT,
    item_description TEXT,
    sku TEXT,
    quantity REAL,
    unit TEXT,
    weight_kg REAL,
    carton_count INTEGER,
    pallet_count INTEGER,
    source_document TEXT
);

CREATE TABLE warehouse_receipts (
    id INTEGER PRIMARY KEY,
    shipment_id INTEGER REFERENCES shipments(id),
    receipt_number TEXT,
    received_date DATE,
    warehouse TEXT,
    received_by TEXT
);

CREATE TABLE receipt_items (
    id INTEGER PRIMARY KEY,
    receipt_id INTEGER REFERENCES warehouse_receipts(id),
    item_description TEXT,
    sku TEXT,
    quantity_received REAL,
    unit TEXT,
    condition TEXT CHECK(condition IN ('good','damaged','partial')) DEFAULT 'good',
    damage_notes TEXT,
    photo_path TEXT
);

CREATE TABLE reconciliation_results (
    id INTEGER PRIMARY KEY,
    shipment_id INTEGER REFERENCES shipments(id),
    manifest_item_id INTEGER REFERENCES manifest_items(id),
    receipt_item_id INTEGER REFERENCES receipt_items(id),
    match_confidence REAL,
    quantity_manifest REAL,
    quantity_received REAL,
    variance REAL,
    status TEXT CHECK(status IN ('matched','shortage','overage','damaged','unmatched_manifest','unmatched_receipt')) DEFAULT 'matched',
    notes TEXT,
    reconciled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Testing Criteria

- [ ] Parses a standard shipping manifest PDF and extracts all line items with quantities
- [ ] Auto-matches 90%+ of items between a manifest and warehouse receipt for a clean shipment
- [ ] Correctly identifies a 10-unit shortage when receipt quantity < manifest quantity
- [ ] Handles LCL deconsolidation — reconciles items for 3 different consignees from one container
- [ ] Fuzzy matching correctly links "Ladies Cotton T-Shirt Blue" (manifest) to "Women's Blue Cotton Tee" (receipt)
- [ ] Generates a reconciliation report with matched, short, and excess items summarized
- [ ] OCR successfully extracts data from a scanned packing list with >85% field accuracy

## Implementation Notes

- Document parsing pipeline: PDF → text extraction (pdfplumber) → structured data extraction (regex + LLM) → normalization → database insertion
- For OCR'd documents, run a two-pass approach: Tesseract for text extraction, then LLM for field identification and structuring
- Matching algorithm: first pass by exact SKU match, second pass by fuzzy description match (rapidfuzz, threshold 80%), third pass by LLM semantic matching for remaining unmatched items
- LCL reconciliation: group manifest items by House B/L number first, then reconcile each consignee's items separately
- Unit conversion: maintain a conversion table (1 carton = X pieces, 1 pallet = Y cartons) per product category to catch unit-based discrepancies
- Memory budget: ~4GB (LLM for description matching; pandas DataFrames for batch reconciliation)
- For high-volume operations, implement batch processing: queue incoming documents and reconcile in background with status tracking
- Consider adding a barcode/QR scanning feature for warehouse staff to scan items during receipt for real-time reconciliation
