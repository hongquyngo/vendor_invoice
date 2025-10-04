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
    Enhanced with PO level data and legacy invoice detection
    """
    try:
        engine = get_db_engine()
        
        # Enhanced query with legacy invoice detection
        query = """
        WITH legacy_invoices AS (
            -- Calculate legacy invoices per PO line (arrival_detail_id IS NULL)
            SELECT 
                pid.product_purchase_order_id,
                SUM(pid.purchased_invoice_quantity) as legacy_invoice_qty,
                COUNT(DISTINCT pid.purchase_invoice_id) as legacy_invoice_count
            FROM purchase_invoice_details pid
            JOIN purchase_invoices pi ON pid.purchase_invoice_id = pi.id
            WHERE pid.arrival_detail_id IS NULL  -- Legacy invoices only
                AND pid.delete_flag = 0
                AND pi.delete_flag = 0
            GROUP BY pid.product_purchase_order_id
        )
        SELECT 
            -- AN/CAN Info
            can.can_line_id,
            can.arrival_note_number,
            can.arrival_date,
            can.creator,
            can.days_since_arrival,
            can.created_date,
            
            -- Vendor Info
            can.vendor,
            can.vendor_code,
            can.vendor_type,
            can.vendor_location_type,
            
            -- Entity Info
            can.consignee AS legal_entity,
            can.consignee_code AS legal_entity_code,
            
            -- PO Info
            can.po_number,
            can.po_type,
            can.external_ref_number,
            can.payment_term,
            can.product_purchase_order_id,
            
            -- Product Info
            can.product_name,
            can.pt_code,
            can.brand,
            can.package_size,
            can.standard_uom,
            can.buying_uom,
            can.uom_conversion,
            
            -- AN Level Quantity Info
            can.arrival_quantity,
            can.uninvoiced_quantity,
            can.total_invoiced_quantity,
            can.invoice_status,
            
            -- Cost Info
            can.buying_unit_cost,
            can.standard_unit_cost,
            can.landed_cost,
            can.landed_cost_usd,
            
            -- Calculate invoice value
            ROUND(can.uninvoiced_quantity * 
                  CAST(SUBSTRING_INDEX(can.buying_unit_cost, ' ', 1) AS DECIMAL(15,2)), 2
            ) AS estimated_invoice_value,

            -- Extract currency
            SUBSTRING_INDEX(can.buying_unit_cost, ' ', -1) AS currency,
            
            -- VAT information
            COALESCE(ppo.vat_gst, 0) AS vat_percent,
            ROUND(can.uninvoiced_quantity * 
                  CAST(SUBSTRING_INDEX(can.buying_unit_cost, ' ', 1) AS DECIMAL(15,2)) * 
                  COALESCE(ppo.vat_gst, 0) / 100, 2
            ) AS vat_amount,
            
            -- PO Line Level Status Information
            can.po_line_status,
            can.po_line_is_over_delivered,
            can.po_line_is_over_invoiced,
            can.po_line_arrival_completion_percent,
            can.po_line_invoice_completion_percent,
            can.po_line_pending_invoiced_qty,

            -- PO Quantities
            ppo.purchase_quantity AS po_buying_quantity,
            ppo.quantity AS po_standard_quantity,
            
            -- Legacy Invoice Information
            COALESCE(li.legacy_invoice_qty, 0) AS legacy_invoice_qty,
            COALESCE(li.legacy_invoice_count, 0) AS legacy_invoice_count,
            
            -- Calculate true remaining considering legacy
            GREATEST(
                0,
                LEAST(
                    can.uninvoiced_quantity,
                    can.po_line_pending_invoiced_qty
                )
            ) AS true_remaining_qty,
            
            -- Flag if has legacy invoices
            CASE 
                WHEN COALESCE(li.legacy_invoice_qty, 0) > 0 THEN 'Y' 
                ELSE 'N' 
            END AS has_legacy_invoices
            
        FROM can_tracking_full_view can
        JOIN product_purchase_orders ppo ON can.product_purchase_order_id = ppo.id
        LEFT JOIN legacy_invoices li ON li.product_purchase_order_id = ppo.id
        WHERE can.uninvoiced_quantity > 0
        """
        
        # Add filters
        conditions = []
        params = {}
        
        if filters:
            if filters.get('creators'):
                conditions.append("can.creator IN :creators")
                params['creators'] = tuple(filters['creators'])
            
            if filters.get('vendor_types'):
                conditions.append("can.vendor_type IN :vendor_types")
                params['vendor_types'] = tuple(filters['vendor_types'])
            
            if filters.get('vendors'):
                conditions.append("can.vendor_code IN :vendors")
                params['vendors'] = tuple(filters['vendors'])
            
            if filters.get('entities'):
                conditions.append("can.consignee_code IN :entities")
                params['entities'] = tuple(filters['entities'])
            
            if filters.get('brands'):
                conditions.append("can.brand IN :brands")
                params['brands'] = tuple(filters['brands'])
            
            if filters.get('arrival_date_from'):
                conditions.append("can.arrival_date >= :arrival_date_from")
                params['arrival_date_from'] = filters['arrival_date_from']
            
            if filters.get('arrival_date_to'):
                conditions.append("can.arrival_date <= :arrival_date_to")
                params['arrival_date_to'] = filters['arrival_date_to']
            
            if filters.get('created_date_from'):
                conditions.append("can.created_date >= :created_date_from")
                params['created_date_from'] = filters['created_date_from']
            
            if filters.get('created_date_to'):
                conditions.append("can.created_date <= :created_date_to")
                params['created_date_to'] = filters['created_date_to']
            
            if filters.get('an_numbers'):
                conditions.append("can.arrival_note_number IN :an_numbers")
                params['an_numbers'] = tuple(filters['an_numbers'])
            
            if filters.get('po_numbers'):
                conditions.append("can.po_number IN :po_numbers")
                params['po_numbers'] = tuple(filters['po_numbers'])
            
            if filters.get('po_line_statuses'):
                conditions.append("can.po_line_status IN :po_line_statuses")
                params['po_line_statuses'] = tuple(filters['po_line_statuses'])
            
            if filters.get('show_over_delivered'):
                conditions.append("can.po_line_is_over_delivered = 'Y'")
            
            if filters.get('show_over_invoiced'):
                conditions.append("can.po_line_is_over_invoiced = 'Y'")
            
            if filters.get('show_has_legacy'):
                conditions.append("COALESCE(li.legacy_invoice_qty, 0) > 0")
            
            if filters.get('arrival_completion_min') is not None:
                conditions.append("can.po_line_arrival_completion_percent >= :arrival_completion_min")
                params['arrival_completion_min'] = filters['arrival_completion_min']
            
            if filters.get('arrival_completion_max') is not None:
                conditions.append("can.po_line_arrival_completion_percent <= :arrival_completion_max")
                params['arrival_completion_max'] = filters['arrival_completion_max']
            
            if filters.get('invoice_completion_min') is not None:
                conditions.append("can.po_line_invoice_completion_percent >= :invoice_completion_min")
                params['invoice_completion_min'] = filters['invoice_completion_min']
            
            if filters.get('invoice_completion_max') is not None:
                conditions.append("can.po_line_invoice_completion_percent <= :invoice_completion_max")
                params['invoice_completion_max'] = filters['invoice_completion_max']
        
        # Add conditions to query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY can.arrival_date DESC, can.arrival_note_number DESC"
        
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
            'po_line_statuses': sorted(df['po_line_status'].dropna().unique().tolist())
        }
        
        return options
        
    except Exception as e:
        logger.error(f"Error getting filter options: {e}")
        return {
            'creators': [], 'vendor_types': [], 'vendors': [], 'entities': [],
            'brands': [], 'an_numbers': [], 'po_numbers': [], 'po_line_statuses': []
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
            can.payment_term,
            po.currency_id AS po_currency_id,
            c.code AS po_currency_code,
            po.seller_company_id AS vendor_id,
            po.buyer_company_id AS entity_id,
            po.payment_term_id,
            pt.name AS payment_term_name,
            po.id AS purchase_order_id,
            ppo.id AS product_purchase_order_id,
            ad.id AS arrival_detail_id
        FROM can_tracking_full_view can
        JOIN purchase_orders po ON can.po_number = po.po_number
        JOIN product_purchase_orders ppo ON ppo.purchase_order_id = po.id 
            AND ppo.product_id = (SELECT id FROM products WHERE pt_code = can.pt_code LIMIT 1)
        JOIN arrival_details ad ON ad.id = can.can_line_id
        JOIN currencies c ON po.currency_id = c.id
        LEFT JOIN payment_terms pt ON po.payment_term_id = pt.id
        WHERE can.can_line_id IN :can_line_ids
            AND po.delete_flag = 0
        """
        
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={'can_line_ids': tuple(can_line_ids)})
        
        if not df.empty:
            df['payment_term_days'] = df['payment_term_name'].apply(calculate_days_from_term_name)
        
        return df
        
    except Exception as e:
        logger.error(f"Error getting invoice details: {e}")
        return pd.DataFrame()

def validate_invoice_selection(selected_df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Basic validation for selected ANs (used at line 569 in main page)
    
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
    
    # Check single legal entity
    entities = selected_df['legal_entity_code'].unique()
    if len(entities) > 1:
        return False, f"Multiple legal entities selected: {', '.join(entities)}. Please select ANs from a single entity."
    
    return True, ""

# utils/invoice_data.py - Updated create_purchase_invoice function

def create_purchase_invoice(invoice_data: Dict, details_df: pd.DataFrame, user_id: str) -> Tuple[bool, str, Optional[int]]:
    """
    Create purchase invoice with proper VAT field handling
    Updated to handle new fields:
    - total_invoiced_amount_exclude_vat in purchase_invoices
    - amount_exclude_vat and vat_gst in purchase_invoice_details
    """
    engine = get_db_engine()
    
    try:
        with engine.begin() as conn:
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
            
            # Calculate total amounts excluding VAT
            total_amount_exclude_vat = 0
            po_to_invoice_rate = invoice_data.get('po_to_invoice_rate', 1.0)
            
            # First pass: calculate totals
            for _, row in details_df.iterrows():
                unit_cost_str = row['buying_unit_cost']
                unit_cost = float(unit_cost_str.split()[0])
                quantity = row['uninvoiced_quantity']
                
                # Calculate base amount in invoice currency (excluding VAT)
                base_amount_in_invoice_currency = unit_cost * quantity * po_to_invoice_rate
                total_amount_exclude_vat += base_amount_in_invoice_currency
            
            # Prepare header data with both including and excluding VAT amounts
            header_params = {
                'invoice_number': invoice_data['invoice_number'],
                'invoiced_date': invoice_data['invoiced_date'],
                'due_date': invoice_data['due_date'],
                'total_invoiced_amount': invoice_data['total_invoiced_amount'],  # Including VAT
                'total_invoiced_amount_exclude_vat': round(total_amount_exclude_vat, 2),  # Excluding VAT
                'seller_id': invoice_data['seller_id'],
                'buyer_id': invoice_data['buyer_id'],
                'currency_id': invoice_data['currency_id'],
                'payment_term_id': invoice_data['payment_term_id'],
                'created_by': keycloak_id
            }
            
            # Add optional fields
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
            
            # Build INSERT query
            columns = list(header_params.keys())
            values = [f":{key}" for key in columns]
            
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
            
            result = conn.execute(header_query, header_params)
            invoice_id = result.lastrowid
            
            # Insert purchase_invoice_details with VAT fields
            for _, row in details_df.iterrows():
                # Extract unit cost
                unit_cost_str = row['buying_unit_cost']
                unit_cost = float(unit_cost_str.split()[0])
                
                # Get VAT percentage from product_purchase_orders
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
                
                # Calculate amounts
                quantity = row['uninvoiced_quantity']
                
                # Amount excluding VAT in invoice currency
                amount_exclude_vat = round(unit_cost * quantity * po_to_invoice_rate, 2)
                
                # Amount including VAT
                vat_multiplier = 1 + (vat_percent / 100)
                amount_include_vat = round(amount_exclude_vat * vat_multiplier, 2)
                
                detail_params = {
                    'purchase_invoice_id': invoice_id,
                    'purchase_order_id': row['purchase_order_id'],
                    'product_purchase_order_id': row['product_purchase_order_id'],
                    'arrival_detail_id': row['arrival_detail_id'],
                    'purchased_invoice_quantity': quantity,
                    'invoiced_quantity': quantity,
                    'amount': amount_include_vat,  # Amount INCLUDING VAT
                    'amount_exclude_vat': amount_exclude_vat,  # Amount EXCLUDING VAT
                    'vat_gst': vat_percent,  # VAT percentage
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
                    amount_exclude_vat,
                    vat_gst,
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
                    :amount_exclude_vat,
                    :vat_gst,
                    :exchange_rate,
                    0
                )
                """)
                
                conn.execute(detail_query, detail_params)
            
            # Log the successful creation with VAT details
            logger.info(f"""
            Invoice {invoice_data['invoice_number']} created successfully:
            - Total with VAT: {invoice_data['total_invoiced_amount']:,.2f} {invoice_data['invoice_currency_code']}
            - Total without VAT: {total_amount_exclude_vat:,.2f} {invoice_data['invoice_currency_code']}
            - VAT amount: {invoice_data['total_invoiced_amount'] - total_amount_exclude_vat:,.2f} {invoice_data['invoice_currency_code']}
            """)
            
            return True, f"Invoice {invoice_data['invoice_number']} created successfully", invoice_id
            
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        return False, f"Error creating invoice: {str(e)}", None


def generate_invoice_number(vendor_id: int, buyer_id: int, is_advance_payment: bool = False) -> str:
    """Generate unique invoice number"""
    try:
        engine = get_db_engine()
        
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        
        vendor_id = int(vendor_id) if vendor_id is not None else 0
        buyer_id = int(buyer_id) if buyer_id is not None else 0
        
        query = text("""
        SELECT MAX(id) as max_id
        FROM purchase_invoices
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query).fetchone()
            last_id = result[0] if result and result[0] else 0
        
        seq = last_id + 1
        suffix = 'A' if is_advance_payment else 'P'
        
        invoice_number = f"V-INV{date_str}-{vendor_id}{buyer_id}{seq}-{suffix}"
        
        return invoice_number
        
    except Exception as e:
        logger.error(f"Error generating invoice number: {e}")
        vendor_id = int(vendor_id) if vendor_id is not None else 0
        buyer_id = int(buyer_id) if buyer_id is not None else 0
        suffix = 'A' if is_advance_payment else 'P'
        timestamp = datetime.now().strftime('%H%M%S')
        return f"V-INV{datetime.now().strftime('%Y%m%d')}-{vendor_id}{buyer_id}{timestamp}-{suffix}"

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_payment_terms() -> pd.DataFrame:
    """Get available payment terms from database"""
    try:
        engine = get_db_engine()
        
        query = text("""
        SELECT 
            id,
            name,
            COALESCE(description, name) AS description
        FROM payment_terms
        WHERE delete_flag = 0
        ORDER BY name ASC
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        
        if not df.empty:
            df['days'] = df['name'].apply(calculate_days_from_term_name)
            df = df.sort_values(['days', 'name'])
        
        if df.empty:
            df = pd.DataFrame([
                {'id': 1, 'name': 'Net 30', 'days': 30, 'description': 'Payment due in 30 days'},
                {'id': 2, 'name': 'Net 60', 'days': 60, 'description': 'Payment due in 60 days'},
                {'id': 3, 'name': 'Net 90', 'days': 90, 'description': 'Payment due in 90 days'},
                {'id': 4, 'name': 'COD', 'days': 0, 'description': 'Cash on delivery'}
            ])
        
        return df
        
    except Exception as e:
        logger.error(f"Error getting payment terms: {e}")
        return pd.DataFrame([
            {'id': 1, 'name': 'Net 30', 'days': 30, 'description': 'Payment due in 30 days'},
            {'id': 2, 'name': 'Net 60', 'days': 60, 'description': 'Payment due in 60 days'},
            {'id': 3, 'name': 'Net 90', 'days': 90, 'description': 'Payment due in 90 days'},
            {'id': 4, 'name': 'COD', 'days': 0, 'description': 'Cash on delivery'}
        ])

def calculate_days_from_term_name(term_name: str) -> int:
    """Calculate days from payment term name"""
    if pd.isna(term_name):
        return 30
    
    term_name = str(term_name)
    
    if term_name.startswith('Net '):
        try:
            days_str = term_name.replace('Net ', '').split()[0]
            return int(days_str)
        except:
            return 30
    elif term_name in ['COD', 'CIA', 'TT IN ADVANCE'] or 'Advance' in term_name:
        return 0
    else:
        return 30

@st.cache_data(ttl=60)
def get_po_line_summary(po_line_ids: List[int]) -> pd.DataFrame:
    """
    Get PO line level summary including legacy invoice information
    """
    try:
        if not po_line_ids:
            return pd.DataFrame()
        
        engine = get_db_engine()
        
        query = text("""
        WITH legacy_invoices AS (
            SELECT 
                pid.product_purchase_order_id,
                SUM(pid.purchased_invoice_quantity) as legacy_invoice_qty,
                COUNT(DISTINCT pid.purchase_invoice_id) as legacy_invoice_count
            FROM purchase_invoice_details pid
            JOIN purchase_invoices pi ON pid.purchase_invoice_id = pi.id
            WHERE pid.arrival_detail_id IS NULL
                AND pid.delete_flag = 0
                AND pi.delete_flag = 0
                AND pid.product_purchase_order_id IN :po_line_ids
            GROUP BY pid.product_purchase_order_id
        ),
        new_invoices AS (
            SELECT 
                pid.product_purchase_order_id,
                SUM(pid.purchased_invoice_quantity) as new_invoice_qty
            FROM purchase_invoice_details pid
            JOIN purchase_invoices pi ON pid.purchase_invoice_id = pi.id
            WHERE pid.arrival_detail_id IS NOT NULL
                AND pid.delete_flag = 0
                AND pi.delete_flag = 0
                AND pid.product_purchase_order_id IN :po_line_ids
            GROUP BY pid.product_purchase_order_id
        )
        SELECT 
            ppo.id as product_purchase_order_id,
            po.po_number,
            p.pt_code,
            p.name as product_name,
            ppo.purchase_quantity as po_buying_qty,
            COALESCE(li.legacy_invoice_qty, 0) as legacy_invoice_qty,
            COALESCE(ni.new_invoice_qty, 0) as new_invoice_qty,
            ppo.purchase_quantity - (COALESCE(li.legacy_invoice_qty, 0) + COALESCE(ni.new_invoice_qty, 0)) as po_remaining_qty
        FROM product_purchase_orders ppo
        JOIN purchase_orders po ON ppo.purchase_order_id = po.id
        JOIN products p ON ppo.product_id = p.id
        LEFT JOIN legacy_invoices li ON li.product_purchase_order_id = ppo.id
        LEFT JOIN new_invoices ni ON ni.product_purchase_order_id = ppo.id
        WHERE ppo.id IN :po_line_ids
            AND ppo.delete_flag = 0
            AND po.delete_flag = 0
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'po_line_ids': tuple(po_line_ids)})
        
        return df
        
    except Exception as e:
        logger.error(f"Error getting PO line summary: {e}")
        return pd.DataFrame()