# pages/1_📝_Create_Invoice.py

import streamlit as st
import pandas as pd
from datetime import datetime, date
import time

# Import utils
from utils.auth import AuthManager
from utils.invoice_data import (
    get_uninvoiced_ans, 
    get_filter_options,
    get_invoice_details,
    validate_invoice_selection,
    create_purchase_invoice,
    generate_invoice_number,
    get_payment_terms,
    calculate_days_from_term_name
)
from utils.invoice_service import InvoiceService
from utils.currency_utils import (
    get_available_currencies,
    calculate_exchange_rates,
    format_exchange_rate,
    get_invoice_amounts_in_currency
)

# Page config
st.set_page_config(
    page_title="Create Purchase Invoice",
    page_icon="📝",
    layout="wide"
)

# Initialize
auth = AuthManager()
auth.require_auth()
service = InvoiceService()

# Initialize session state
if 'selected_ans' not in st.session_state:
    st.session_state.selected_ans = []
if 'wizard_step' not in st.session_state:
    st.session_state.wizard_step = 'select'  # 'select', 'preview', 'confirm'
if 'select_all' not in st.session_state:
    st.session_state.select_all = False
if 'invoice_data' not in st.session_state:
    st.session_state.invoice_data = None
if 'details_df' not in st.session_state:
    st.session_state.details_df = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'items_per_page' not in st.session_state:
    st.session_state.items_per_page = 50  # Default items per page
if 'is_advance_payment' not in st.session_state:
    st.session_state.is_advance_payment = False

def main():
    st.title("📝 Create Purchase Invoice")
    
    # Progress indicator
    show_progress_indicator()
    
    # Show current step based on wizard state
    if st.session_state.wizard_step == 'select':
        show_an_selection()
    elif st.session_state.wizard_step == 'preview':
        show_invoice_preview()
    elif st.session_state.wizard_step == 'confirm':
        show_invoice_confirm()

def show_progress_indicator():
    """Show wizard progress"""
    steps = {
        'select': 1,
        'preview': 2,
        'confirm': 3
    }
    
    current_step = steps.get(st.session_state.wizard_step, 1)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if current_step >= 1:
            st.success("✅ Step 1: Select ANs")
        else:
            st.info("⭕ Step 1: Select ANs")
    
    with col2:
        if current_step >= 2:
            st.success("✅ Step 2: Review Invoice")
        elif current_step == 2:
            st.info("🔵 Step 2: Review Invoice")
        else:
            st.info("⭕ Step 2: Review Invoice")
    
    with col3:
        if current_step >= 3:
            st.success("✅ Step 3: Confirm & Submit")
        elif current_step == 3:
            st.info("🔵 Step 3: Confirm & Submit")
        else:
            st.info("⭕ Step 3: Confirm & Submit")
    
    st.markdown("---")

def show_an_selection():
    """Step 1: AN Selection"""
    
    # Filters section
    with st.expander("🔍 Filters", expanded=True):
        filter_options = get_filter_options()
        
        # Row 1: Vendor, Legal Entity
        col1, col2 = st.columns(2)
        
        with col1:
            vendor_options = [f"{code} - {name}" for code, name in filter_options['vendors']]
            selected_vendors = st.multiselect(
                "Vendor",
                options=vendor_options,
                placeholder="Choose an option",
                key="filter_vendor"
            )
            vendor_codes = [v.split(' - ')[0] for v in selected_vendors]
        
        with col2:
            entity_options = [f"{code} - {name}" for code, name in filter_options['entities']]
            selected_entities = st.multiselect(
                "Legal Entity",
                options=entity_options,
                placeholder="Choose an option",
                key="filter_entity"
            )
            entity_codes = [e.split(' - ')[0] for e in selected_entities]
        
        # Row 2: AN Number, PO Number, Creator, Brand
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            an_numbers = st.multiselect(
                "Search AN Number",
                options=filter_options['an_numbers'],
                placeholder="Choose an option",
                key="filter_an"
            )
        
        with col2:
            po_numbers = st.multiselect(
                "Search PO Number", 
                options=filter_options['po_numbers'],
                placeholder="Choose an option",
                key="filter_po"
            )
        
        with col3:
            creators = st.multiselect(
                "Creator",
                options=filter_options['creators'],
                placeholder="Choose an option",
                key="filter_creator"
            )
        
        with col4:
            brands = st.multiselect(
                "Brand",
                options=filter_options['brands'],
                placeholder="Choose an option",
                key="filter_brand"
            )
        
        # Date Filters Section
        st.markdown("##### Date Filters")
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 0.5])
        
        with col1:
            arrival_date_from = st.date_input(
                "Arrival From",
                value=None,
                key="filter_arrival_date_from"
            )
        
        with col2:
            arrival_date_to = st.date_input(
                "Arrival To",
                value=None,
                key="filter_arrival_date_to"
            )
        
        with col3:
            created_date_from = st.date_input(
                "Created From",
                value=None,
                key="filter_created_date_from"
            )
        
        with col4:
            created_date_to = st.date_input(
                "Created To",
                value=None,
                key="filter_created_date_to"
            )
        
        with col5:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Reset Filters", use_container_width=True):
                for key in st.session_state:
                    if key.startswith('filter_'):
                        del st.session_state[key]
                st.session_state.select_all = False
                st.session_state.current_page = 1  # Reset to first page
                st.rerun()
        
        # Advanced filters
        st.markdown("---")
        show_advanced = st.checkbox("Show Advanced Filters")
        if show_advanced:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                vendor_types = st.multiselect(
                    "Vendor Type",
                    options=filter_options['vendor_types'],
                    placeholder="Choose an option",
                    key="filter_vendor_type"
                )
            
            with col2:
                # PO Line Status filter
                po_statuses = st.multiselect(
                    "PO Line Status",
                    options=filter_options.get('po_line_statuses', []),
                    placeholder="Choose status",
                    key="filter_po_line_status",
                    help="Filter by PO line completion status"
                )
            
            with col3:
                # Checkbox filters for problematic lines
                st.markdown("**Flag Filters**")
                show_over_delivered = st.checkbox(
                    "Show Over-delivered Lines",
                    key="filter_over_delivered",
                    help="Show only PO lines with over-delivery"
                )
                show_over_invoiced = st.checkbox(
                    "Show Over-invoiced Lines", 
                    key="filter_over_invoiced",
                    help="Show only PO lines with over-invoicing"
                )
            
            # Completion percentage filters
            st.markdown("**Completion Percentage Filters**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                arrival_min = st.number_input(
                    "Arrival % Min",
                    min_value=0.0,
                    max_value=100.0,
                    value=None,
                    key="filter_arrival_min",
                    help="Minimum arrival completion percentage"
                )
            
            with col2:
                arrival_max = st.number_input(
                    "Arrival % Max",
                    min_value=0.0,
                    max_value=200.0,
                    value=None,
                    key="filter_arrival_max",
                    help="Maximum arrival completion percentage"
                )
            
            with col3:
                invoice_min = st.number_input(
                    "Invoice % Min",
                    min_value=0.0,
                    max_value=100.0,
                    value=None,
                    key="filter_invoice_min",
                    help="Minimum invoice completion percentage"
                )
            
            with col4:
                invoice_max = st.number_input(
                    "Invoice % Max",
                    min_value=0.0,
                    max_value=200.0,
                    value=None,
                    key="filter_invoice_max",
                    help="Maximum invoice completion percentage"
                )
    
    # Build filters
    filters = {}
    if vendor_codes:
        filters['vendors'] = vendor_codes
    if entity_codes:
        filters['entities'] = entity_codes
    if an_numbers:
        filters['an_numbers'] = an_numbers
    if po_numbers:
        filters['po_numbers'] = po_numbers
    if creators:
        filters['creators'] = creators
    if brands:
        filters['brands'] = brands
    if arrival_date_from:
        filters['arrival_date_from'] = arrival_date_from
    if arrival_date_to:
        filters['arrival_date_to'] = arrival_date_to
    if created_date_from:
        filters['created_date_from'] = created_date_from
    if created_date_to:
        filters['created_date_to'] = created_date_to
    if 'filter_vendor_type' in st.session_state and st.session_state.filter_vendor_type:
        filters['vendor_types'] = st.session_state.filter_vendor_type
    
    # Add PO Line Status filters
    if 'filter_po_line_status' in st.session_state and st.session_state.filter_po_line_status:
        filters['po_line_statuses'] = st.session_state.filter_po_line_status
    if 'filter_over_delivered' in st.session_state and st.session_state.filter_over_delivered:
        filters['show_over_delivered'] = True
    if 'filter_over_invoiced' in st.session_state and st.session_state.filter_over_invoiced:
        filters['show_over_invoiced'] = True
    if 'filter_arrival_min' in st.session_state and st.session_state.filter_arrival_min is not None:
        filters['arrival_completion_min'] = st.session_state.filter_arrival_min
    if 'filter_arrival_max' in st.session_state and st.session_state.filter_arrival_max is not None:
        filters['arrival_completion_max'] = st.session_state.filter_arrival_max
    if 'filter_invoice_min' in st.session_state and st.session_state.filter_invoice_min is not None:
        filters['invoice_completion_min'] = st.session_state.filter_invoice_min
    if 'filter_invoice_max' in st.session_state and st.session_state.filter_invoice_max is not None:
        filters['invoice_completion_max'] = st.session_state.filter_invoice_max
    
    # Get data
    df = get_uninvoiced_ans(filters)
    
    # Display results with pagination
    total_items = len(df)
    
    # Pagination controls header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"### 📊 Available ANs ({total_items} items)")
    
    with col2:
        items_per_page_options = [25, 50, 100, 200]
        items_per_page = st.selectbox(
            "Items per page",
            options=items_per_page_options,
            index=items_per_page_options.index(st.session_state.items_per_page),
            key="items_per_page_select"
        )
        if items_per_page != st.session_state.items_per_page:
            st.session_state.items_per_page = items_per_page
            st.session_state.current_page = 1
            st.rerun()
    
    if df.empty:
        st.info("No uninvoiced ANs found with the selected filters.")
    else:
        # Calculate pagination
        total_pages = (total_items + st.session_state.items_per_page - 1) // st.session_state.items_per_page
        
        # Ensure current page is valid
        if st.session_state.current_page > total_pages:
            st.session_state.current_page = total_pages
        if st.session_state.current_page < 1:
            st.session_state.current_page = 1
        
        # Calculate slice for current page
        start_idx = (st.session_state.current_page - 1) * st.session_state.items_per_page
        end_idx = min(start_idx + st.session_state.items_per_page, total_items)
        
        # Slice dataframe for current page
        page_df = df.iloc[start_idx:end_idx]
        
        # Use container for scrollable area
        with st.container():
            # Header row with select all checkbox
            cols = st.columns([0.5, 1.2, 1.2, 2, 2, 1.2, 1, 1, 1, 1, 1.5])
            
            # Select all checkbox in header - now only for current page
            header_checkbox = cols[0].checkbox(
                "",
                key="header_select_all",
                value=st.session_state.select_all
            )
            
            # If header checkbox state changed, update items on current page
            if header_checkbox != st.session_state.select_all:
                st.session_state.select_all = header_checkbox
                if header_checkbox:
                    # Add all items from current page
                    page_ids = page_df['can_line_id'].tolist()
                    for id in page_ids:
                        if id not in st.session_state.selected_ans:
                            st.session_state.selected_ans.append(id)
                else:
                    # Remove all items from current page
                    page_ids = page_df['can_line_id'].tolist()
                    st.session_state.selected_ans = [id for id in st.session_state.selected_ans if id not in page_ids]
                st.rerun()
            
            cols[1].markdown("**AN Number**")
            cols[2].markdown("**PO Number**")
            cols[3].markdown("**Vendor**")
            cols[4].markdown("**Product**")
            cols[5].markdown("**Uninv Qty**")
            cols[6].markdown("**Unit Cost**")
            cols[7].markdown("**VAT**")
            cols[8].markdown("**Est. Value**")
            cols[9].markdown("**Payment**")
            cols[10].markdown("**PO Status**")
            
            st.markdown("---")
            
            # Data rows
            for idx, row in page_df.iterrows():
                cols = st.columns([0.5, 1.2, 1.2, 2, 2, 1.2, 1, 1, 1, 1, 1.5])
                
                # Checkbox
                is_selected = cols[0].checkbox(
                    "",
                    key=f"select_{row['can_line_id']}_page{st.session_state.current_page}",
                    value=row['can_line_id'] in st.session_state.selected_ans,
                    label_visibility="collapsed"
                )
                
                if is_selected and row['can_line_id'] not in st.session_state.selected_ans:
                    st.session_state.selected_ans.append(row['can_line_id'])
                elif not is_selected and row['can_line_id'] in st.session_state.selected_ans:
                    st.session_state.selected_ans.remove(row['can_line_id'])
                
                # Display data
                cols[1].text(row['arrival_note_number'])
                cols[2].text(row['po_number'])
                cols[3].text(f"{row['vendor_code']} - {row['vendor']}")
                cols[4].text(f"{row['pt_code']} - {row['product_name']}")
                cols[5].text(f"{row['uninvoiced_quantity']:.2f} {row['buying_uom']}")
                cols[6].text(row['buying_unit_cost'])
                
                # Display VAT
                vat_percent = row.get('vat_percent', 0)
                cols[7].text(f"{vat_percent:.0f}%")
                
                currency = row['buying_unit_cost'].split()[-1] if ' ' in str(row['buying_unit_cost']) else 'USD'
                cols[8].text(f"{row['estimated_invoice_value']:,.2f} {currency}")
                cols[9].text(row.get('payment_term', 'N/A'))
                
                # Display PO Line Status with color coding
                po_status = row.get('po_line_status', 'UNKNOWN')
                status_color = {
                    'COMPLETED': '🟢',
                    'OVER_DELIVERED': '🔴',
                    'PENDING': '⚪',
                    'PENDING_INVOICING': '🟡',
                    'PENDING_RECEIPT': '🟠',
                    'IN_PROCESS': '🔵',
                    'UNKNOWN_STATUS': '⚫'
                }.get(po_status, '⚫')
                
                # Add indicators for over-delivered/over-invoiced
                indicators = []
                if row.get('po_line_is_over_delivered') == 'Y':
                    indicators.append('OD')
                if row.get('po_line_is_over_invoiced') == 'Y':
                    indicators.append('OI')
                
                status_text = f"{status_color} {po_status[:8]}"
                if indicators:
                    status_text += f" ({','.join(indicators)})"
                
                cols[10].text(status_text)
        
        # Update header checkbox state based on current page selection
        page_ids = page_df['can_line_id'].tolist()
        page_selected = [id for id in page_ids if id in st.session_state.selected_ans]
        if len(page_selected) == 0:
            st.session_state.select_all = False
        elif len(page_selected) == len(page_ids):
            st.session_state.select_all = True
        
        # Pagination controls
        st.markdown("---")
        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
        
        with col1:
            if st.button("⏮ First", disabled=st.session_state.current_page == 1, use_container_width=True):
                st.session_state.current_page = 1
                st.session_state.select_all = False
                st.rerun()
        
        with col2:
            if st.button("◀️ Previous", disabled=st.session_state.current_page == 1, use_container_width=True):
                st.session_state.current_page -= 1
                st.session_state.select_all = False
                st.rerun()
        
        with col3:
            st.markdown(f"<div style='text-align: center; padding: 8px;'>Page {st.session_state.current_page} of {total_pages}</div>", unsafe_allow_html=True)
        
        with col4:
            if st.button("Next ▶️", disabled=st.session_state.current_page == total_pages, use_container_width=True):
                st.session_state.current_page += 1
                st.session_state.select_all = False
                st.rerun()
        
        with col5:
            if st.button("Last ⏭", disabled=st.session_state.current_page == total_pages, use_container_width=True):
                st.session_state.current_page = total_pages
                st.session_state.select_all = False
                st.rerun()
        
        # Summary and actions
        if st.session_state.selected_ans:
            # Get selected items from full dataframe
            selected_df = df[df['can_line_id'].isin(st.session_state.selected_ans)]
            totals = service.calculate_invoice_totals(selected_df)
            
            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Selected ANs", totals['an_count'])
            col2.metric("Total Quantity", f"{totals['total_quantity']:,.2f}")
            col3.metric("Total Lines", totals['total_lines'])
            col4.metric("Est. Total Value", f"{totals['total_value']:,.2f} {totals['currency']}")
            
            # Show total VAT amount
            if 'vat_amount' in selected_df.columns:
                total_vat = selected_df['vat_amount'].sum()
                col5.metric("Total VAT", f"{total_vat:,.2f} {totals['currency']}")
            
            # Show warnings if any
            payment_terms = selected_df['payment_term'].dropna().unique()
            if len(payment_terms) > 1:
                st.warning(f"⚠️ Multiple payment terms found: {', '.join(payment_terms)}. The most common term will be used.")
            
            # Check for multiple VAT rates
            vat_rates = selected_df['vat_percent'].unique()
            if len(vat_rates) > 1:
                st.info(f"ℹ️ Multiple VAT rates found: {', '.join([f'{v:.0f}%' for v in vat_rates])}. Each line will retain its respective VAT rate.")
            
            # Check for over-delivered/over-invoiced lines
            if 'po_line_is_over_delivered' in selected_df.columns:
                over_delivered = selected_df[selected_df['po_line_is_over_delivered'] == 'Y']
                if not over_delivered.empty:
                    st.warning(f"⚠️ {len(over_delivered)} PO line(s) have over-delivery. Please review before proceeding.")
            
            if 'po_line_is_over_invoiced' in selected_df.columns:
                over_invoiced = selected_df[selected_df['po_line_is_over_invoiced'] == 'Y']
                if not over_invoiced.empty:
                    st.warning(f"⚠️ {len(over_invoiced)} PO line(s) have over-invoicing. Please review before proceeding.")
            
            # Show summary by PO line status if available
            if 'po_line_status' in selected_df.columns:
                status_summary = selected_df.groupby('po_line_status').size()
                if len(status_summary) > 1 or status_summary.index[0] not in ['PENDING_INVOICING', 'IN_PROCESS']:
                    with st.expander("📊 PO Line Status Summary"):
                        for status, count in status_summary.items():
                            status_emoji = {
                                'COMPLETED': '🟢',
                                'OVER_DELIVERED': '🔴',
                                'PENDING': '⚪',
                                'PENDING_INVOICING': '🟡', 
                                'PENDING_RECEIPT': '🟠',
                                'IN_PROCESS': '🔵',
                                'UNKNOWN_STATUS': '⚫'
                            }.get(status, '⚫')
                            st.text(f"{status_emoji} {status}: {count} line(s)")
            
            # Validate selection
            is_valid, error_msg = service.can_lines_be_invoiced_together(selected_df)
            
            st.markdown("---")
            if not is_valid:
                st.error(f"❌ {error_msg}")
            else:
                st.success("✅ Selected items can be invoiced together")
                if st.button("➡️ Proceed to Preview", type="primary", use_container_width=True):
                    # Store selected data
                    st.session_state.selected_df = selected_df
                    st.session_state.wizard_step = 'preview'
                    st.rerun()

def show_invoice_preview():
    """Step 2: Invoice Preview"""
    
    # Check if we have selected data
    if 'selected_df' not in st.session_state or st.session_state.selected_df is None:
        st.error("No data found. Please go back and select ANs.")
        if st.button("⬅️ Back to Selection"):
            st.session_state.wizard_step = 'select'
            st.rerun()
        return
    
    selected_df = st.session_state.selected_df
    
    # Get detailed info
    with st.spinner("Loading invoice details..."):
        details_df = get_invoice_details(st.session_state.selected_ans)
    
    if details_df.empty:
        st.error("Could not load invoice details. Please try again.")
        if st.button("⬅️ Back to Selection"):
            st.session_state.wizard_step = 'select'
            st.rerun()
        return
    
    # Store details for next step
    st.session_state.details_df = details_df
    
    # Get PO currency info
    po_currency_id = details_df['po_currency_id'].iloc[0] if not details_df.empty else 1
    po_currency_code = details_df['po_currency_code'].iloc[0] if not details_df.empty else 'USD'
    
    # Invoice header section
    st.markdown("### 📄 Invoice Information")
    
    # Advance Payment checkbox - OUTSIDE THE FORM for immediate refresh
    col1, col2 = st.columns(2)
    
    with col1:
        # Store current state
        current_advance_state = st.session_state.is_advance_payment
        
        # Checkbox outside form
        advance_payment = st.checkbox(
            "Advance Payment Invoice",
            value=st.session_state.is_advance_payment,
            key="advance_payment_toggle",
            help="Check this for advance payment invoices (PI). This will change the invoice number suffix."
        )
        
        # Check if state changed and trigger refresh
        if advance_payment != current_advance_state:
            st.session_state.is_advance_payment = advance_payment
            st.rerun()
    
    # Generate invoice number based on current advance payment state
    vendor_code = selected_df['vendor_code'].iloc[0]
    vendor_id = details_df['vendor_id'].iloc[0] if not details_df.empty else None
    buyer_id = details_df['entity_id'].iloc[0] if not details_df.empty else None
    
    invoice_number = generate_invoice_number(vendor_id, buyer_id, st.session_state.is_advance_payment)
    
    # Show invoice type indicator
    with col2:
        if st.session_state.is_advance_payment:
            st.info("🔵 **Invoice Type: Advance Payment (PI)**")
        else:
            st.success("🟢 **Invoice Type: Commercial Invoice (CI)**")
    
    # Currency selection section
    st.markdown("### 💱 Currency Selection")
    
    # Get available currencies
    currencies_df = get_available_currencies()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"**PO Currency:** {po_currency_code}")
    
    with col2:
        # Currency selection dropdown
        currency_options = currencies_df['code'].tolist()
        currency_display = [f"{row['code']} - {row['name']}" for _, row in currencies_df.iterrows()]
        
        # Default to PO currency if available, otherwise USD
        default_index = 0
        if po_currency_code in currency_options:
            default_index = currency_options.index(po_currency_code)
        elif 'USD' in currency_options:
            default_index = currency_options.index('USD')
        
        selected_currency_display = st.selectbox(
            "Invoice Currency",
            options=currency_display,
            index=default_index,
            key="invoice_currency_select",
            help="Select the currency for this invoice"
        )
        
        # Extract currency code
        invoice_currency_code = selected_currency_display.split(' - ')[0]
        invoice_currency_id = currencies_df[currencies_df['code'] == invoice_currency_code]['id'].iloc[0]
    
    with col3:
        # Calculate and display exchange rates
        if po_currency_code != invoice_currency_code:
            with st.spinner("Fetching exchange rates..."):
                rates = calculate_exchange_rates(po_currency_code, invoice_currency_code)
            
            st.markdown("**Exchange Rates:**")
            st.text(f"1 {po_currency_code} = {format_exchange_rate(rates['po_to_invoice_rate'])} {invoice_currency_code}")
            if invoice_currency_code != 'USD':
                st.text(f"1 USD = {format_exchange_rate(rates['usd_exchange_rate'])} {invoice_currency_code}")
        else:
            rates = {'po_to_invoice_rate': 1.0, 'usd_exchange_rate': 1.0 if invoice_currency_code == 'USD' else None}
            st.success("✅ Same currency - No conversion needed")
    
    # Store selected currency and rates in session state
    st.session_state.invoice_currency_code = invoice_currency_code
    st.session_state.invoice_currency_id = invoice_currency_id
    st.session_state.exchange_rates = rates
    
    # Invoice form
    with st.form("invoice_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Invoice Number", value=invoice_number, disabled=True, key="invoice_number")
            
            invoice_date = st.date_input(
                "Invoice Date",
                value=date.today(),
                key="invoice_date"
            )
            
            # Payment terms
            unique_payment_terms_from_selected = selected_df['payment_term'].dropna().unique().tolist()
            
            # Build payment term options
            term_options = {}
            default_term_name = None
            
            if unique_payment_terms_from_selected:
                # Get all payment terms data for reference
                all_payment_terms_df = get_payment_terms()
                
                # Get the most common payment term from selected ANs
                most_common_term = selected_df['payment_term'].mode()
                if not most_common_term.empty:
                    default_term_name = most_common_term.iloc[0]
                
                # Build options from selected AN payment terms
                for term_name in unique_payment_terms_from_selected:
                    # Look up in database
                    db_match = all_payment_terms_df[all_payment_terms_df['name'] == term_name]
                    
                    if not db_match.empty:
                        row = db_match.iloc[0]
                        term_options[term_name] = {
                            'id': int(row['id']),
                            'days': int(row['days']),
                            'description': row.get('description', '')
                        }
                    else:
                        # Not in database - calculate days and use a default ID
                        days = calculate_days_from_term_name(term_name)
                        # Try to find ID from details_df if available
                        term_id = 1  # Default
                        if not details_df.empty and 'payment_term_id' in details_df.columns:
                            # Find matching row in details
                            detail_match = details_df[details_df.get('payment_term_name', '') == term_name]
                            if not detail_match.empty:
                                term_id = int(detail_match.iloc[0]['payment_term_id'])
                        
                        term_options[term_name] = {
                            'id': term_id,
                            'days': days,
                            'description': f'{term_name} ({days} days)'
                        }
            else:
                # No payment terms found - use a default
                st.warning("⚠️ No payment terms found in selected ANs. Using default.")
                term_options = {
                    'Net 30': {'id': 1, 'days': 30, 'description': 'Payment due in 30 days'}
                }
                default_term_name = 'Net 30'
            
            # Get list of term names for dropdown
            term_names = list(term_options.keys())
            
            # Set default index
            default_index = 0
            if default_term_name and default_term_name in term_names:
                default_index = term_names.index(default_term_name)
            
            selected_term = st.selectbox(
                "Payment Terms",
                options=term_names,
                index=default_index,
                key="payment_terms",
                help=f"Payment terms from selected ANs ({len(term_names)} option(s) available)"
            )
            
            if term_options[selected_term].get('description'):
                st.caption(term_options[selected_term]['description'])
        
        with col2:
            # Commercial Invoice input - disabled if advance payment
            commercial_inv = st.text_input(
                "Commercial Invoice No.",
                key="commercial_invoice_no",
                disabled=st.session_state.is_advance_payment,
                placeholder="Required for Commercial Invoices" if not st.session_state.is_advance_payment else "Not required for Advance Payment"
            )
            
            if st.session_state.is_advance_payment:
                st.caption("💡 Commercial invoice number not required for advance payments")
            else:
                st.caption("⚠️ Required field for commercial invoices")
            
            # Calculate due date
            term_days = term_options[selected_term]['days']
            due_date = service.calculate_due_date(invoice_date, term_days)
            
            st.date_input(
                "Due Date",
                value=due_date,
                key="due_date",
                help=f"Calculated based on {selected_term} ({term_days} days)"
            )
            
            email_accountant = st.checkbox(
                "Email to Accountant",
                value=False,
                key="email_to_accountant"
            )
        
        # Summary table with VAT
        st.markdown("### 📊 Invoice Summary")
        
        # Calculate amounts in selected currency
        if po_currency_code != invoice_currency_code:
            # Need conversion
            converted_amounts = get_invoice_amounts_in_currency(
                selected_df,
                po_currency_code,
                invoice_currency_code
            )
            
            # Update selected_df display with converted amounts
            summary_df = service.prepare_invoice_summary(selected_df)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            # Show conversion info
            st.info(f"💱 Amounts converted from {po_currency_code} to {invoice_currency_code} at rate: {format_exchange_rate(converted_amounts['exchange_rate'])}")
            
            totals = converted_amounts
        else:
            # No conversion needed
            summary_df = service.prepare_invoice_summary(selected_df)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            totals = service.calculate_invoice_totals_with_vat(selected_df)
            totals['currency'] = invoice_currency_code
        
        # Totals display
        col1, col2, col3 = st.columns([2, 1, 1])
        with col3:
            st.markdown("**Invoice Totals**")
            st.text(f"Lines: {len(selected_df)}")
            st.text(f"Quantity: {selected_df['uninvoiced_quantity'].sum():,.2f}")
            st.text(f"Subtotal: {totals['subtotal']:,.2f} {totals['currency']}")
            st.text(f"VAT: {totals['total_vat']:,.2f} {totals['currency']}")
            st.text(f"Total: {totals['total_with_vat']:,.2f} {totals['currency']}")
        
        # Store totals for next step
        st.session_state.invoice_totals = totals
        
        # Form actions
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            back_btn = st.form_submit_button("⬅️ Back", use_container_width=True)
        
        with col3:
            proceed_btn = st.form_submit_button(
                "✅ Review & Confirm", 
                type="primary", 
                use_container_width=True
            )
    
    # Handle form submission
    if back_btn:
        st.session_state.wizard_step = 'select'
        st.rerun()
    
    if proceed_btn:
        # Validate Commercial Invoice number if not advance payment
        if not st.session_state.is_advance_payment and not st.session_state.commercial_invoice_no:
            st.error("❌ Commercial Invoice Number is required for Commercial Invoices")
            return
        
        # Get USD exchange rate
        if invoice_currency_code == 'USD':
            usd_rate = 1.0
        else:
            usd_rate = rates.get('usd_exchange_rate', 1.0)
        
        # Prepare invoice data with proper exchange rates
        st.session_state.invoice_data = {
            'invoice_number': invoice_number,
            'commercial_invoice_no': st.session_state.commercial_invoice_no if not st.session_state.is_advance_payment else '',
            'invoiced_date': st.session_state.invoice_date,
            'due_date': st.session_state.due_date,
            'total_invoiced_amount': totals['total_with_vat'],
            'currency_id': st.session_state.invoice_currency_id,
            'usd_exchange_rate': usd_rate,
            'seller_id': details_df['vendor_id'].iloc[0] if not details_df.empty else None,
            'buyer_id': details_df['entity_id'].iloc[0] if not details_df.empty else None,
            'payment_term_id': term_options[st.session_state.payment_terms]['id'],
            'email_to_accountant': 1 if st.session_state.email_to_accountant else 0,
            'created_by': st.session_state.username,
            'invoice_type': 'PROFORMA_INVOICE' if st.session_state.is_advance_payment else 'COMMERCIAL_INVOICE',
            'advance_payment': 1 if st.session_state.is_advance_payment else 0,
            'po_currency_code': po_currency_code,
            'invoice_currency_code': invoice_currency_code,
            'po_to_invoice_rate': rates.get('po_to_invoice_rate', 1.0)
        }
        st.session_state.wizard_step = 'confirm'
        st.rerun()

def show_invoice_confirm():
    """Step 3: Confirm and Submit"""
    
    # Check if we have invoice data
    if not st.session_state.get('invoice_data') or not st.session_state.get('details_df') is not None:
        st.error("No invoice data found. Please go back and complete the preview.")
        if st.button("⬅️ Back to Preview"):
            st.session_state.wizard_step = 'preview'
            st.rerun()
        return
    
    invoice_data = st.session_state.invoice_data
    details_df = st.session_state.details_df
    
    st.markdown("### ✅ Confirm and Submit")
    
    # Display final summary
    payment_terms_dict = service.get_payment_terms_dict()
    payment_term_name = payment_terms_dict.get(
        invoice_data['payment_term_id'], {}
    ).get('name', 'N/A')
    
    # Invoice details card
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📋 Invoice Details")
            invoice_type = "Advance Payment (PI)" if invoice_data.get('invoice_type') == 'PROFORMA_INVOICE' else "Commercial Invoice (CI)"
            st.text(f"Invoice Type: {invoice_type}")
            st.text(f"Invoice Number: {invoice_data['invoice_number']}")
            st.text(f"Invoice Date: {invoice_data['invoiced_date']}")
            st.text(f"Due Date: {invoice_data['due_date']}")
            st.text(f"Payment Terms: {payment_term_name}")
            if invoice_data.get('commercial_invoice_no'):
                st.text(f"Commercial Invoice: {invoice_data['commercial_invoice_no']}")
        
        with col2:
            st.markdown("#### 💰 Summary")
            st.text(f"Total Amount: {invoice_data['total_invoiced_amount']:,.2f}")
            st.text(f"Invoice Currency: {invoice_data['invoice_currency_code']}")
            st.text(f"PO Currency: {invoice_data['po_currency_code']}")
            if invoice_data['po_currency_code'] != invoice_data['invoice_currency_code']:
                st.text(f"Exchange Rate: {format_exchange_rate(invoice_data['po_to_invoice_rate'])}")
            st.text(f"Lines: {len(details_df)}")
            st.text(f"Email to Accountant: {'Yes' if invoice_data['email_to_accountant'] else 'No'}")
    
    # Exchange rate information
    if invoice_data['invoice_currency_code'] != 'USD':
        st.info(f"💱 USD Exchange Rate: 1 USD = {format_exchange_rate(invoice_data['usd_exchange_rate'])} {invoice_data['invoice_currency_code']}")
    
    # Line items
    st.markdown("### 📋 Line Items")
    
    # Add VAT information to display
    selected_df = st.session_state.selected_df
    df_display = pd.merge(
        details_df[['arrival_detail_id', 'arrival_note_number', 'po_number', 'product_name', 'uninvoiced_quantity', 'buying_unit_cost']],
        selected_df[['can_line_id', 'vat_percent']],
        left_on='arrival_detail_id',
        right_on='can_line_id',
        how='left'
    )
    
    # Format for display with currency conversion
    df_display = df_display[['arrival_note_number', 'po_number', 'product_name', 
                            'uninvoiced_quantity', 'buying_unit_cost', 'vat_percent']].copy()
    
    # Convert unit costs if needed
    if invoice_data['po_currency_code'] != invoice_data['invoice_currency_code']:
        df_display['converted_unit_cost'] = df_display['buying_unit_cost'].apply(
            lambda x: f"{float(x.split()[0]) * invoice_data['po_to_invoice_rate']:,.2f} {invoice_data['invoice_currency_code']}"
        )
        df_display['vat_percent'] = df_display['vat_percent'].apply(lambda x: f"{x:.0f}%")
        df_display.columns = ['AN Number', 'PO Number', 'Product', 'Quantity', 'Original Cost', 'VAT', 'Invoice Cost']
        display_cols = ['AN Number', 'PO Number', 'Product', 'Quantity', 'Original Cost', 'Invoice Cost', 'VAT']
    else:
        df_display['vat_percent'] = df_display['vat_percent'].apply(lambda x: f"{x:.0f}%")
        df_display.columns = ['AN Number', 'PO Number', 'Product', 'Quantity', 'Unit Cost', 'VAT']
        display_cols = ['AN Number', 'PO Number', 'Product', 'Quantity', 'Unit Cost', 'VAT']
    
    st.dataframe(df_display[display_cols], use_container_width=True, hide_index=True)
    
    # Show total breakdown
    if hasattr(st.session_state, 'invoice_totals'):
        totals = st.session_state.invoice_totals
        col1, col2, col3 = st.columns(3)
        with col3:
            st.markdown("**Final Totals**")
            st.text(f"Subtotal: {totals['subtotal']:,.2f} {totals['currency']}")
            st.text(f"VAT: {totals['total_vat']:,.2f} {totals['currency']}")
            st.text(f"Total: {totals['total_with_vat']:,.2f} {totals['currency']}")
    
    # Warning
    st.warning("⚠️ Please review the information above carefully. This action cannot be undone.")
    
    # Actions
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("⬅️ Back to Preview", use_container_width=True):
            st.session_state.wizard_step = 'preview'
            st.rerun()
    
    with col3:
        if st.button("💾 Create Invoice", type="primary", use_container_width=True):
            # Create invoice with proper exchange rates
            with st.spinner("Creating invoice..."):
                success, message, invoice_id = create_purchase_invoice(
                    invoice_data,
                    st.session_state.details_df,
                    st.session_state.username
                )
                
                if success:
                    # Success dialog
                    st.success(f"✅ {message}")
                    st.balloons()
                    
                    # Show success details
                    with st.container():
                        invoice_type = "Advance Payment (PI)" if invoice_data.get('invoice_type') == 'PROFORMA_INVOICE' else "Commercial Invoice (CI)"
                        st.info(f"""
                        **Invoice Created Successfully!**
                        - Invoice Type: {invoice_type}
                        - Invoice ID: {invoice_id}
                        - Invoice Number: {invoice_data['invoice_number']}
                        - Currency: {invoice_data['invoice_currency_code']}
                        - Payment Terms: {payment_term_name}
                        - Total Amount: {invoice_data['total_invoiced_amount']:,.2f} {invoice_data['invoice_currency_code']}
                        """)
                        
                        # Options
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("📝 Create Another Invoice", use_container_width=True):
                                # Reset all session state
                                st.session_state.selected_ans = []
                                st.session_state.wizard_step = 'select'
                                st.session_state.select_all = False
                                st.session_state.invoice_data = None
                                st.session_state.details_df = None
                                st.session_state.selected_df = None
                                st.session_state.current_page = 1  # Reset to first page
                                st.session_state.is_advance_payment = False  # Reset advance payment state
                                st.session_state.invoice_currency_code = None
                                st.session_state.invoice_currency_id = None
                                st.session_state.exchange_rates = None
                                st.session_state.invoice_totals = None
                                st.rerun()
                        
                        with col2:
                            if st.button("📊 View Invoice History", use_container_width=True):
                                st.switch_page("pages/2_📊_Invoice_History.py")
                else:
                    st.error(f"❌ {message}")

if __name__ == "__main__":
    main()