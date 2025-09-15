# utils/invoice_data.py

import pandas as pd
from sqlalchemy import text
import streamlit as st
from datetime import datetime, date
import logging
from typing import List, Dict, Optional, Tuple
from .db import get_db_engine

logger = logging.getLogger(__name__)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_uninvoiced_ans(filters: Dict = None) -> pd.DataFrame:
    """
    Get all ANs with uninvoiced quantity
    
    Args:
        filters: Dictionary of filters to apply
        
    Returns:
        DataFrame with uninvoiced ANs
    """
    try:
        engine = get_db_engine()
        
        # Base query - now includes payment_term, VAT, and PO line status fields
        query = """
        SELECT 
            -- AN/CAN Info
            can_line_id,
            arrival_note_number,
            arrival_date,
            creator,
            days_since_arrival,
            
            -- Vendor Info
            vendor,
            vendor_code,
            vendor_type,
            vendor_location_type,
            
            -- Entity Info
            consignee AS legal_entity,
            consignee_code AS legal_entity_code,
            
            -- PO Info
            po_number,
            po_type,
            external_ref_number,
            payment_term,  -- Payment term
            
            -- Product Info
            product_name,
            pt_code,
            brand,
            package_size,
            standard_uom,
            buying_uom,
            uom_conversion,
            
            -- Quantity Info
            arrival_quantity,
            uninvoiced_quantity,
            total_invoiced_quantity,
            invoice_status,
            
            -- Cost Info
            buying_unit_cost,
            standard_unit_cost,
            landed_cost,
            landed_cost_usd,
            usd_landed_cost_currency_exchange_rate,
            
            -- Calculate invoice value
            ROUND(uninvoiced_quantity * 
                  CAST(SUBSTRING_INDEX(buying_unit_cost, ' ', 1) AS DECIMAL(15,2)), 2
            ) AS estimated_invoice_value,

            -- Extract currency from buying_unit_cost
            SUBSTRING_INDEX(buying_unit_cost, ' ', -1) AS currency,
            
            -- VAT information from PO
            COALESCE(ppo.vat_gst, 0) AS vat_percent,
            -- Calculate VAT amount
            ROUND(uninvoiced_quantity * 
                  CAST(SUBSTRING_INDEX(buying_unit_cost, ' ', 1) AS DECIMAL(15,2)) * 
                  COALESCE(ppo.vat_gst, 0) / 100, 2
            ) AS vat_amount,
            -- Total with VAT
            ROUND(uninvoiced_quantity * 
                  CAST(SUBSTRING_INDEX(buying_unit_cost, ' ', 1) AS DECIMAL(15,2)) * 
                  (1 + COALESCE(ppo.vat_gst, 0) / 100), 2
            ) AS total_with_vat,
            
            -- PO Line Status Information
            po_line_status,
            po_line_is_over_delivered,
            po_line_is_over_invoiced,
            po_line_arrival_completion_percent,
            po_line_invoice_completion_percent,
            po_line_total_arrived_qty,
            po_line_total_invoiced_buying_qty,
            po_line_total_invoiced_standard_qty,
            po_line_pending_invoiced_qty,
            po_line_pending_arrival_qty
            
        FROM can_tracking_full_view can
        JOIN product_purchase_orders ppo ON can.product_purchase_order_id = ppo.id
        WHERE uninvoiced_quantity > 0
        """
        
        # Add filters
        conditions = []
        params = {}
        
        if filters:
            if filters.get('creators'):
                conditions.append("creator IN :creators")
                params['creators'] = tuple(filters['creators'])
            
            if filters.get('vendor_types'):
                conditions.append("vendor_type IN :vendor_types")
                params['vendor_types'] = tuple(filters['vendor_types'])
            
            if filters.get('vendors'):
                conditions.append("vendor_code IN :vendors")
                params['vendors'] = tuple(filters['vendors'])
            
            if filters.get('entities'):
                conditions.append("consignee_code IN :entities")
                params['entities'] = tuple(filters['entities'])
            
            if filters.get('brands'):
                conditions.append("brand IN :brands")
                params['brands'] = tuple(filters['brands'])
            
            if filters.get('arrival_date_from'):
                conditions.append("arrival_date >= :arrival_date_from")
                params['arrival_date_from'] = filters['arrival_date_from']
            
            if filters.get('arrival_date_to'):
                conditions.append("arrival_date <= :arrival_date_to")
                params['arrival_date_to'] = filters['arrival_date_to']
            
            if filters.get('created_date_from'):
                conditions.append("created_date >= :created_date_from")
                params['created_date_from'] = filters['created_date_from']
            
            if filters.get('created_date_to'):
                conditions.append("created_date <= :created_date_to")
                params['created_date_to'] = filters['created_date_to']
            
            if filters.get('an_numbers'):
                conditions.append("arrival_note_number IN :an_numbers")
                params['an_numbers'] = tuple(filters['an_numbers'])
            
            if filters.get('po_numbers'):
                conditions.append("po_number IN :po_numbers")
                params['po_numbers'] = tuple(filters['po_numbers'])
            
            # New PO Line Status filters
            if filters.get('po_line_statuses'):
                conditions.append("po_line_status IN :po_line_statuses")
                params['po_line_statuses'] = tuple(filters['po_line_statuses'])
            
            if filters.get('show_over_delivered'):
                conditions.append("po_line_is_over_delivered = 'Y'")
            
            if filters.get('show_over_invoiced'):
                conditions.append("po_line_is_over_invoiced = 'Y'")
            
            # Filter by completion percentage ranges
            if filters.get('arrival_completion_min') is not None:
                conditions.append("po_line_arrival_completion_percent >= :arrival_completion_min")
                params['arrival_completion_min'] = filters['arrival_completion_min']
            
            if filters.get('arrival_completion_max') is not None:
                conditions.append("po_line_arrival_completion_percent <= :arrival_completion_max")
                params['arrival_completion_max'] = filters['arrival_completion_max']
            
            if filters.get('invoice_completion_min') is not None:
                conditions.append("po_line_invoice_completion_percent >= :invoice_completion_min")
                params['invoice_completion_min'] = filters['invoice_completion_min']
            
            if filters.get('invoice_completion_max') is not None:
                conditions.append("po_line_invoice_completion_percent <= :invoice_completion_max")
                params['invoice_completion_max'] = filters['invoice_completion_max']
        
        # Add conditions to query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY arrival_date DESC, arrival_note_number DESC"
        
        # Execute query
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching uninvoiced ANs: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_filter_options() -> Dict:
    """Get unique values for filters"""
    try:
        engine = get_db_engine()
        
        # Get all filter options including PO line status
        query = text("""
        SELECT 
            DISTINCT creator,
            vendor_type,
            vendor_code,
            vendor,
            consignee_code,
            consignee,
            brand,
            arrival_note_number,
            po_number,
            po_line_status
        FROM can_tracking_full_view
        WHERE uninvoiced_quantity > 0
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        
        # Process results
        options = {
            'creators': sorted(df['creator'].dropna().unique().tolist()),
            'vendor_types': sorted(df['vendor_type'].dropna().unique().tolist()),
            'vendors': sorted([(row['vendor_code'], row['vendor']) 
                              for _, row in df[['vendor_code', 'vendor']].drop_duplicates().iterrows()]),
            'entities': sorted([(row['consignee_code'], row['consignee']) 
                               for _, row in df[['consignee_code', 'consignee']].drop_duplicates().iterrows()]),
            'brands': sorted(df['brand'].dropna().unique().tolist()),
            'an_numbers': sorted(df['arrival_note_number'].dropna().unique().tolist()),
            'po_numbers': sorted(df['po_number'].dropna().unique().tolist()),
            'po_line_statuses': sorted(df['po_line_status'].dropna().unique().tolist())  # New field
        }
        
        return options
        
    except Exception as e:
        logger.error(f"Error getting filter options: {e}")
        return {
            'creators': [],
            'vendor_types': [],
            'vendors': [],
            'entities': [],
            'brands': [],
            'an_numbers': [],
            'po_numbers': [],
            'po_line_statuses': []
        }

def get_invoice_details(can_line_ids: List[int]) -> pd.DataFrame:
    """Get detailed information for selected CAN lines"""
    try:
        engine = get_db_engine()
        
        query = """
        SELECT 
            can.can_line_id,
            can.arrival_note_number,
            can.po_number,
            can.vendor_code,
            can.vendor,
            can.product_name,
            can.pt_code,
            can.buying_uom,
            can.uninvoiced_quantity,
            can.buying_unit_cost,
            can.payment_term,  -- Payment term from CAN view
            can.po_line_status,  -- Include PO line status
            can.po_line_is_over_delivered,
            can.po_line_is_over_invoiced,
            po.currency_id AS po_currency_id,
            c.code AS po_currency_code,
            po.seller_company_id AS vendor_id,
            po.buyer_company_id AS entity_id,
            po.payment_term_id,
            pt.name AS payment_term_name,  -- Get payment term name
            po.id AS purchase_order_id,
            ppo.id AS product_purchase_order_id,
            ad.id AS arrival_detail_id
        FROM can_tracking_full_view can
        JOIN purchase_orders po ON can.po_number = po.po_number
        JOIN product_purchase_orders ppo ON ppo.purchase_order_id = po.id 
            AND ppo.product_id = (SELECT id FROM products WHERE pt_code = can.pt_code LIMIT 1)
        JOIN arrival_details ad ON ad.id = can.can_line_id
        JOIN currencies c ON po.currency_id = c.id
        LEFT JOIN payment_terms pt ON po.payment_term_id = pt.id  -- Join payment terms table
        WHERE can.can_line_id IN :can_line_ids
        AND po.delete_flag = 0
        """
        
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={'can_line_ids': tuple(can_line_ids)})
        
        # Calculate payment_term_days from the name
        if not df.empty:
            df['payment_term_days'] = df['payment_term_name'].apply(calculate_days_from_term_name)
        
        return df
        
    except Exception as e:
        logger.error(f"Error getting invoice details: {e}")
        return pd.DataFrame()

def calculate_days_from_term_name(term_name: str) -> int:
    """Calculate days from payment term name"""
    if pd.isna(term_name):
        return 30
    
    term_name = str(term_name)
    
    # Handle common patterns
    if term_name.startswith('Net '):
        try:
            # Extract number after "Net "
            days_str = term_name.replace('Net ', '').split()[0]
            return int(days_str)
        except:
            return 30
    elif term_name in ['COD', 'CIA', 'TT IN ADVANCE'] or 'Advance' in term_name:
        return 0
    else:
        return 30  # Default

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_payment_terms() -> pd.DataFrame:
    """Get available payment terms from database"""
    try:
        engine = get_db_engine()
        
        # Simple query to get the data first
        simple_query = text("""
        SELECT 
            id,
            name,
            COALESCE(description, name) AS description
        FROM payment_terms
        WHERE delete_flag = 0
        ORDER BY name ASC
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(simple_query, conn)
        
        # Calculate days from name in Python
        if not df.empty:
            df['days'] = df['name'].apply(calculate_days_from_term_name)
            # Sort by days
            df = df.sort_values(['days', 'name'])
        
        # If no payment terms found, return a default set
        if df.empty:
            df = pd.DataFrame([
                {'id': 1, 'name': 'Net 30', 'days': 30, 'description': 'Payment due in 30 days'},
                {'id': 2, 'name': 'Net 60', 'days': 60, 'description': 'Payment due in 60 days'},
                {'id': 3, 'name': 'Net 90', 'days': 90, 'description': 'Payment due in 90 days'},
                {'id': 4, 'name': 'COD', 'days': 0, 'description': 'Cash on delivery'},
                {'id': 5, 'name': 'Net 45', 'days': 45, 'description': 'Payment due in 45 days'},
                {'id': 6, 'name': 'TT IN ADVANCE', 'days': 0, 'description': 'Telegraphic transfer in advance'}
            ])
        
        return df
        
    except Exception as e:
        logger.error(f"Error getting payment terms: {e}")
        # Return default payment terms if database query fails
        return pd.DataFrame([
            {'id': 1, 'name': 'Net 30', 'days': 30, 'description': 'Payment due in 30 days'},
            {'id': 2, 'name': 'Net 60', 'days': 60, 'description': 'Payment due in 60 days'},
            {'id': 3, 'name': 'Net 90', 'days': 90, 'description': 'Payment due in 90 days'},
            {'id': 4, 'name': 'COD', 'days': 0, 'description': 'Cash on delivery'},
            {'id': 5, 'name': 'Net 45', 'days': 45, 'description': 'Payment due in 45 days'},
            {'id': 6, 'name': 'TT IN ADVANCE', 'days': 0, 'description': 'Telegraphic transfer in advance'}
        ])

def validate_invoice_selection(selected_df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validate selected ANs for invoice creation
    
    Returns:
        (is_valid, error_message)
    """
    if selected_df.empty:
        return False, "No items selected"
    
    # Check single vendor
    vendors = selected_df['vendor_code'].unique()
    if len(vendors) > 1:
        return False, f"Multiple vendors selected: {', '.join(vendors)}. Please select ANs from a single vendor."
    
    # Check vendor type consistency
    vendor_types = selected_df['vendor_type'].unique()
    if len(vendor_types) > 1:
        return False, "Cannot mix Internal and External vendors in the same invoice"
    
    # Check payment terms consistency
    payment_terms = selected_df['payment_term'].dropna().unique()
    if len(payment_terms) > 1:
        return False, f"Multiple payment terms found: {', '.join(payment_terms)}. Please select ANs with the same payment terms."
    
    # Check for over-delivered/over-invoiced items if they exist
    if 'po_line_is_over_delivered' in selected_df.columns:
        over_delivered = selected_df[selected_df['po_line_is_over_delivered'] == 'Y']
        if not over_delivered.empty:
            logger.warning(f"Found {len(over_delivered)} over-delivered PO lines in selection")
    
    if 'po_line_is_over_invoiced' in selected_df.columns:
        over_invoiced = selected_df[selected_df['po_line_is_over_invoiced'] == 'Y']
        if not over_invoiced.empty:
            logger.warning(f"Found {len(over_invoiced)} over-invoiced PO lines in selection")
    
    return True, ""

def create_purchase_invoice(invoice_data: Dict, details_df: pd.DataFrame, user_id: str) -> Tuple[bool, str, Optional[int]]:
    """
    Create purchase invoice and details
    
    Args:
        invoice_data: Invoice header data
        details_df: Invoice details dataframe
        user_id: Username of the user creating the invoice
    
    Returns:
        (success, message, invoice_id)
    """
    engine = get_db_engine()
    
    try:
        with engine.begin() as conn:
            # Log for debugging
            logger.info(f"Creating invoice with payment_term_id: {invoice_data.get('payment_term_id')}")
            
            # Get keycloak_id from username
            keycloak_query = text("""
            SELECT e.keycloak_id 
            FROM users u
            JOIN employees e ON u.employee_id = e.id
            WHERE u.username = :username
            AND u.delete_flag = 0
            """)
            
            keycloak_result = conn.execute(keycloak_query, {'username': user_id}).fetchone()
            
            if not keycloak_result:
                logger.error(f"Could not find keycloak_id for user: {user_id}")
                return False, f"Invalid user: {user_id}", None
            
            keycloak_id = keycloak_result[0]
            logger.info(f"Found keycloak_id: {keycloak_id} for user: {user_id}")
            
            # Validate payment_term_id exists
            pt_check = text("SELECT id FROM payment_terms WHERE id = :pt_id AND delete_flag = 0")
            pt_result = conn.execute(pt_check, {'pt_id': invoice_data['payment_term_id']}).fetchone()
            
            if not pt_result:
                logger.error(f"Payment term ID {invoice_data['payment_term_id']} not found")
                return False, f"Invalid payment term ID: {invoice_data['payment_term_id']}", None
            
            # Prepare header data - only include non-null values
            header_params = {
                'invoice_number': invoice_data['invoice_number'],
                'invoiced_date': invoice_data['invoiced_date'],
                'due_date': invoice_data['due_date'],
                'total_invoiced_amount': invoice_data['total_invoiced_amount'],
                'seller_id': invoice_data['seller_id'],
                'buyer_id': invoice_data['buyer_id'],
                'currency_id': invoice_data['currency_id'],
                'payment_term_id': invoice_data['payment_term_id'],
                'created_by': keycloak_id  # Use keycloak_id instead of username
            }
            
            # Add optional fields only if they have values
            if invoice_data.get('commercial_invoice_no'):
                header_params['commercial_invoice_no'] = invoice_data['commercial_invoice_no']
            
            if invoice_data.get('usd_exchange_rate') is not None:
                header_params['usd_exchange_rate'] = invoice_data['usd_exchange_rate']
            
            if invoice_data.get('invoice_type'):
                header_params['invoice_type'] = invoice_data['invoice_type']
            
            if invoice_data.get('email_to_accountant') is not None:
                header_params['email_to_accountant'] = invoice_data['email_to_accountant']
            
            if invoice_data.get('advance_payment') is not None:
                header_params['advance_payment'] = invoice_data['advance_payment']
            
            # Build INSERT query with explicit column list
            columns = []
            values = []
            params_dict = {}
            
            for key, value in header_params.items():
                columns.append(key)
                values.append(f":{key}")
                params_dict[key] = value
            
            header_query = text(f"""
            INSERT INTO purchase_invoices (
                {', '.join(columns)},
                created_date,
                delete_flag
            ) VALUES (
                {', '.join(values)},
                NOW(),
                0
            )
            """)
            
            result = conn.execute(header_query, params_dict)
            invoice_id = result.lastrowid
            
            # 2. Insert purchase_invoice_details
            for _, row in details_df.iterrows():
                # Extract unit cost from string format
                unit_cost_str = row['buying_unit_cost']
                unit_cost = float(unit_cost_str.split()[0])
                
                # Get exchange rate
                po_to_invoice_rate = invoice_data.get('po_to_invoice_rate', 1.0)
                
                # Get VAT percentage from product_purchase_orders table
                vat_percent = 0
                if 'product_purchase_order_id' in row and row['product_purchase_order_id']:
                    vat_query = text("""
                    SELECT vat_gst 
                    FROM product_purchase_orders 
                    WHERE id = :ppo_id 
                    AND delete_flag = 0
                    """)
                    vat_result = conn.execute(vat_query, {'ppo_id': row['product_purchase_order_id']}).fetchone()
                    if vat_result and vat_result[0] is not None:
                        vat_percent = float(vat_result[0])
                
                # Calculate amount INCLUDING VAT (to match existing data pattern)
                base_amount = unit_cost * row['uninvoiced_quantity'] * po_to_invoice_rate
                vat_multiplier = 1 + (vat_percent / 100)
                amount = base_amount * vat_multiplier
                
                # Prepare detail parameters
                detail_params = {
                    'purchase_invoice_id': invoice_id,
                    'purchase_order_id': row['purchase_order_id'],
                    'product_purchase_order_id': row['product_purchase_order_id'],
                    'arrival_detail_id': row['arrival_detail_id'],
                    'purchased_invoice_quantity': row['uninvoiced_quantity'],
                    'invoiced_quantity': row['uninvoiced_quantity'],
                    'amount': amount,
                    'exchange_rate': po_to_invoice_rate
                }
                
                detail_query = text("""
                INSERT INTO purchase_invoice_details (
                    purchase_invoice_id,
                    purchase_order_id,
                    product_purchase_order_id,
                    arrival_detail_id,
                    purchased_invoice_quantity,
                    invoiced_quantity,
                    amount,
                    exchange_rate,
                    delete_flag
                ) VALUES (
                    :purchase_invoice_id,
                    :purchase_order_id,
                    :product_purchase_order_id,
                    :arrival_detail_id,
                    :purchased_invoice_quantity,
                    :invoiced_quantity,
                    :amount,
                    :exchange_rate,
                    0
                )
                """)
                
                conn.execute(detail_query, detail_params)
            
            # Log PO line status if over-delivered/over-invoiced items were included
            if 'po_line_status' in details_df.columns:
                problematic_lines = details_df[
                    (details_df['po_line_is_over_delivered'] == 'Y') | 
                    (details_df['po_line_is_over_invoiced'] == 'Y')
                ]
                if not problematic_lines.empty:
                    logger.info(f"Invoice {invoice_id} includes {len(problematic_lines)} over-delivered/over-invoiced PO lines")
            
            # Commit is handled by context manager
            return True, f"Invoice {invoice_data['invoice_number']} created successfully", invoice_id
            
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        return False, f"Error creating invoice: {str(e)}", None

def generate_invoice_number(vendor_id: int, buyer_id: int, is_advance_payment: bool = False) -> str:
    """
    Generate unique invoice number with NEW format: V-INVYYYYMMDD-ABC-D
    Where:
        A: VendorId
        B: BuyerId  
        C: Auto-increment number (based on max invoice ID + 1)
        D: 'A' for Advance Payment or 'P' for Commercial Invoice
    """
    try:
        engine = get_db_engine()
        
        # Get current date
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        
        # Handle None values - use 0 as placeholder
        vendor_id = int(vendor_id) if vendor_id is not None else 0
        buyer_id = int(buyer_id) if buyer_id is not None else 0
        
        # Get the last id from purchase_invoices table
        query = text("""
        SELECT MAX(id) as max_id
        FROM purchase_invoices
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query).fetchone()
            last_id = result[0] if result and result[0] else 0
        
        # Generate sequence number (last id + 1)
        seq = last_id + 1
        
        # Determine invoice type suffix
        suffix = 'A' if is_advance_payment else 'P'
        
        # Format: V-INVYYYYMMDD-ABC-D
        invoice_number = f"V-INV{date_str}-{vendor_id}{buyer_id}{seq}-{suffix}"
        
        return invoice_number
        
    except Exception as e:
        logger.error(f"Error generating invoice number: {e}")
        
        # Fallback format
        vendor_id = int(vendor_id) if vendor_id is not None else 0
        buyer_id = int(buyer_id) if buyer_id is not None else 0
        suffix = 'A' if is_advance_payment else 'P'
        
        # Use timestamp in sequence position for uniqueness
        timestamp = datetime.now().strftime('%H%M%S')
        fallback_number = f"V-INV{datetime.now().strftime('%Y%m%d')}-{vendor_id}{buyer_id}{timestamp}-{suffix}"
        
        return fallback_number

@st.cache_data(ttl=300)
def get_recent_invoices(limit: int = 100) -> pd.DataFrame:
    """Get recent invoices for history view"""
    try:
        engine = get_db_engine()
        
        query = text("""
        SELECT 
            pi.id,
            pi.invoice_number,
            pi.commercial_invoice_no,
            pi.invoiced_date,
            pi.due_date,
            pi.total_invoiced_amount,
            c.english_name AS vendor,
            curr.code AS currency,
            pt.name AS payment_term,
            pi.created_by,
            pi.created_date,
            COUNT(DISTINCT pid.id) AS line_count,
            COUNT(DISTINCT pid.purchase_order_id) AS po_count
        FROM purchase_invoices pi
        JOIN companies c ON pi.seller_id = c.id
        JOIN currencies curr ON pi.currency_id = curr.id
        LEFT JOIN payment_terms pt ON pi.payment_term_id = pt.id
        LEFT JOIN purchase_invoice_details pid ON pi.id = pid.purchase_invoice_id
        WHERE pi.delete_flag = 0
        GROUP BY pi.id
        ORDER BY pi.created_date DESC
        LIMIT :limit
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'limit': limit})
        
        return df
        
    except Exception as e:
        logger.error(f"Error fetching recent invoices: {e}")
        return pd.DataFrame()