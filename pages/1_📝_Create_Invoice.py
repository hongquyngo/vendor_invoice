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
    calculate_days_from_term_name,
    get_po_line_summary
)
from utils.invoice_service import InvoiceService
from utils.currency_utils import (
    get_available_currencies,
    calculate_exchange_rates,
    validate_exchange_rates,
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
    st.session_state.wizard_step = 'select'
if 'select_all' not in st.session_state:
    st.session_state.select_all = False
if 'invoice_data' not in st.session_state:
    st.session_state.invoice_data = None
if 'details_df' not in st.session_state:
    st.session_state.details_df = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'items_per_page' not in st.session_state:
    st.session_state.items_per_page = 50
if 'is_advance_payment' not in st.session_state:
    st.session_state.is_advance_payment = False
if 'show_po_analysis' not in st.session_state:
    st.session_state.show_po_analysis = False
if 'invoice_creating' not in st.session_state:
    st.session_state.invoice_creating = False
if 'last_created_invoice' not in st.session_state:
    st.session_state.last_created_invoice = None

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
    """Step 1: AN Selection with Enhanced PO Level Information"""
    
    # Show success message if just created an invoice
    if st.session_state.last_created_invoice:
        invoice_info = st.session_state.last_created_invoice
        st.success(f"""
        ✅ **Invoice Created Successfully!**
        - Invoice Number: {invoice_info['number']}
        - Invoice ID: {invoice_info['id']}
        - Total Amount: {invoice_info['amount']:,.2f} {invoice_info['currency']}
        """)
        
        # Clear the message after showing
        st.session_state.last_created_invoice = None
        st.markdown("---")
    
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
                for key in list(st.session_state.keys()):
                    if key.startswith('filter_'):
                        del st.session_state[key]
                st.session_state.select_all = False
                st.session_state.current_page = 1
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
                po_statuses = st.multiselect(
                    "PO Line Status",
                    options=filter_options.get('po_line_statuses', []),
                    placeholder="Choose status",
                    key="filter_po_line_status",
                    help="Filter by PO line completion status"
                )
            
            with col3:
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
                show_legacy_invoices = st.checkbox(
                    "Show Lines with Legacy Invoices",
                    key="filter_has_legacy",
                    help="Show PO lines that have legacy invoices without arrival mapping"
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
    if 'filter_po_line_status' in st.session_state and st.session_state.filter_po_line_status:
        filters['po_line_statuses'] = st.session_state.filter_po_line_status
    if 'filter_over_delivered' in st.session_state and st.session_state.filter_over_delivered:
        filters['show_over_delivered'] = True
    if 'filter_over_invoiced' in st.session_state and st.session_state.filter_over_invoiced:
        filters['show_over_invoiced'] = True
    if 'filter_has_legacy' in st.session_state and st.session_state.filter_has_legacy:
        filters['show_has_legacy'] = True
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
    
    with col3:
        st.session_state.show_po_analysis = st.checkbox(
            "Show PO Analysis",
            value=st.session_state.show_po_analysis,
            help="Display detailed PO line level information"
        )
    
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
            # Determine columns based on view mode
            if st.session_state.show_po_analysis:
                cols = st.columns([0.5, 1, 1, 1.5, 1.5, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 1, 1])
                
                # Header
                cols[0].checkbox("", key="header_select_all", value=st.session_state.select_all)
                cols[1].markdown("**AN Number**")
                cols[2].markdown("**PO Number**")
                cols[3].markdown("**Vendor**")
                cols[4].markdown("**Product**")
                cols[5].markdown("**PO Qty**", help="Original PO line quantity")
                cols[6].markdown("**PO Pend**", help="PO qty minus all invoices (legacy + new)")
                cols[7].markdown("**AN Uninv**", help="Uninvoiced quantity from this AN")
                cols[8].markdown("**Legacy**", help="Legacy invoices without AN mapping")
                cols[9].markdown("**True Qty**", help="Actual remaining qty considering PO limits")
                cols[10].markdown("**Unit Cost**")
                cols[11].markdown("**VAT**")
                cols[12].markdown("**Est. Value**")
                cols[13].markdown("**Status/Risk**")
            else:
                cols = st.columns([0.5, 1.2, 1.2, 2, 2, 1.2, 1, 1, 1, 1, 1.5])
                
                # Header
                cols[0].checkbox("", key="header_select_all", value=st.session_state.select_all)
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
            
            # Handle select all checkbox
            if st.session_state.header_select_all != st.session_state.select_all:
                st.session_state.select_all = st.session_state.header_select_all
                if st.session_state.header_select_all:
                    page_ids = page_df['can_line_id'].tolist()
                    for id in page_ids:
                        if id not in st.session_state.selected_ans:
                            st.session_state.selected_ans.append(id)
                else:
                    page_ids = page_df['can_line_id'].tolist()
                    st.session_state.selected_ans = [id for id in st.session_state.selected_ans if id not in page_ids]
                st.rerun()
            
            st.markdown("---")
            
            # Data rows
            for idx, row in page_df.iterrows():
                if st.session_state.show_po_analysis:
                    display_row_with_po_analysis(row)
                else:
                    display_standard_row(row)
        
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
            selected_df = df[df['can_line_id'].isin(st.session_state.selected_ans)]
            
            if 'product_purchase_order_id' in selected_df.columns:
                po_line_ids = selected_df['product_purchase_order_id'].unique().tolist()
                po_summary_df = get_po_line_summary(po_line_ids)
            else:
                po_summary_df = pd.DataFrame()
            
            totals = service.calculate_invoice_totals(selected_df)
            
            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Selected ANs", totals['an_count'])
            col2.metric("Total Quantity", f"{totals['total_quantity']:,.2f}")
            col3.metric("Total Lines", totals['total_lines'])
            col4.metric("Est. Total Value", f"{totals['total_value']:,.2f} {totals['currency']}")
            
            if 'vat_amount' in selected_df.columns:
                total_vat = selected_df['vat_amount'].sum()
                col5.metric("Total VAT", f"{total_vat:,.2f} {totals['currency']}")
            
            # Show PO Line Risk Analysis
            if st.session_state.show_po_analysis and not po_summary_df.empty:
                with st.expander("📊 PO Line Risk Analysis", expanded=True):
                    for _, po_line in po_summary_df.iterrows():
                        col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
                        
                        with col1:
                            st.markdown(f"**PO #{po_line['po_number']} - {po_line['product_name'][:30]}**")
                            st.text(f"PO Line ID: {po_line['product_purchase_order_id']}")
                        
                        with col2:
                            st.text(f"PO Qty: {po_line.get('po_buying_qty', 0):.0f}")
                            st.text(f"PO Pending: {po_line.get('po_remaining_qty', 0):.0f}")
                            st.text(f"Legacy Inv: {po_line.get('legacy_invoice_qty', 0):.0f}")
                        
                        with col3:
                            selected_for_po = selected_df[selected_df['product_purchase_order_id'] == po_line['product_purchase_order_id']]
                            selected_qty = selected_for_po['uninvoiced_quantity'].sum()
                            
                            st.text(f"Selected AN: {selected_qty:.0f}")
                            remaining_after = po_line.get('po_remaining_qty', 0) - selected_qty
                            st.text(f"After Invoice: {remaining_after:.0f}")
                            
                            if po_line.get('po_buying_qty', 0) > 0:
                                completion = ((po_line.get('po_buying_qty', 0) - remaining_after) / po_line.get('po_buying_qty', 0)) * 100
                                st.text(f"Completion: {completion:.1f}%")
                        
                        with col4:
                            risks = []
                            if po_line.get('legacy_invoice_qty', 0) > 0:
                                risks.append("⚠️ Has Legacy")
                            if selected_qty > po_line.get('po_remaining_qty', 0):
                                risks.append("🔴 Exceeds PO")
                            if 'completion' in locals() and completion > 95:
                                risks.append("⚠️ Near Complete")
                            
                            if risks:
                                for risk in risks:
                                    st.text(risk)
                            else:
                                st.success("✅ No risks")
                        
                        st.markdown("---")
            
            # Show warnings
            payment_terms = selected_df['payment_term'].dropna().unique()
            if len(payment_terms) > 1:
                st.warning(f"⚠️ Multiple payment terms found: {', '.join(payment_terms)}. The most common term will be used.")
            
            vat_rates = selected_df['vat_percent'].unique()
            if len(vat_rates) > 1:
                st.info(f"ℹ️ Multiple VAT rates found: {', '.join([f'{v:.0f}%' for v in vat_rates])}. Each line will retain its respective VAT rate.")
            
            if 'po_line_is_over_delivered' in selected_df.columns:
                over_delivered = selected_df[selected_df['po_line_is_over_delivered'] == 'Y']
                if not over_delivered.empty:
                    st.warning(f"⚠️ {len(over_delivered)} PO line(s) have over-delivery. Please review before proceeding.")
            
            if 'po_line_is_over_invoiced' in selected_df.columns:
                over_invoiced = selected_df[selected_df['po_line_is_over_invoiced'] == 'Y']
                if not over_invoiced.empty:
                    st.warning(f"⚠️ {len(over_invoiced)} PO line(s) have over-invoicing. Please review before proceeding.")
            
            if 'has_legacy_invoices' in selected_df.columns:
                has_legacy = selected_df[selected_df['has_legacy_invoices'] == 'Y']
                if not has_legacy.empty:
                    st.warning(f"⚠️ {len(has_legacy)} PO line(s) have legacy invoices. True remaining quantities will be calculated.")
            
            # Validate selection
            is_valid, error_msg = validate_invoice_selection(selected_df)
            
            st.markdown("---")
            if not is_valid:
                st.error(f"❌ {error_msg}")
            else:
                validation_result, validation_msgs = service.validate_invoice_with_po_level(selected_df)
                
                if not validation_result['can_invoice']:
                    st.error(f"❌ {validation_msgs['error']}")
                else:
                    if validation_msgs.get('warnings'):
                        for warning in validation_msgs['warnings']:
                            st.warning(f"⚠️ {warning}")
                    
                    st.success("✅ Selected items can be invoiced together")
                    
                    if st.button("➡️ Proceed to Preview", type="primary", use_container_width=True):
                        st.session_state.selected_df = selected_df
                        st.session_state.wizard_step = 'preview'
                        st.rerun()

def display_standard_row(row):
    """Display standard row without PO analysis"""
    cols = st.columns([0.5, 1.2, 1.2, 2, 2, 1.2, 1, 1, 1, 1, 1.5])
    
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
    
    cols[1].text(row['arrival_note_number'])
    cols[2].text(row['po_number'])
    cols[3].text(f"{row['vendor_code']} - {row['vendor'][:20]}")
    cols[4].text(f"{row['pt_code']} - {row['product_name'][:20]}")
    cols[5].text(f"{row['uninvoiced_quantity']:.2f} {row['buying_uom']}")
    cols[6].text(row['buying_unit_cost'])
    
    vat_percent = row.get('vat_percent', 0)
    cols[7].text(f"{vat_percent:.0f}%")
    
    currency = row['buying_unit_cost'].split()[-1] if ' ' in str(row['buying_unit_cost']) else 'USD'
    cols[8].text(f"{row['estimated_invoice_value']:,.2f} {currency}")
    cols[9].text(row.get('payment_term', 'N/A'))
    
    po_status = row.get('po_line_status', 'UNKNOWN')
    status_color = get_status_color(po_status)
    
    indicators = []
    if row.get('po_line_is_over_delivered') == 'Y':
        indicators.append('OD')
    if row.get('po_line_is_over_invoiced') == 'Y':
        indicators.append('OI')
    if row.get('has_legacy_invoices') == 'Y':
        indicators.append('LEG')
    
    status_text = f"{status_color} {po_status[:8]}"
    if indicators:
        status_text += f" ({','.join(indicators)})"
    
    cols[10].text(status_text)

def display_row_with_po_analysis(row):
    """Display row with detailed PO analysis"""
    cols = st.columns([0.5, 1, 1, 1.5, 1.5, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7, 1, 1])
    
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
    
    cols[1].text(row['arrival_note_number'][:10])
    cols[2].text(row['po_number'][:10])
    cols[3].text(f"{row['vendor_code'][:3]}-{row['vendor'][:12]}")
    cols[4].text(f"{row['pt_code'][:8]}-{row['product_name'][:12]}")
    
    po_qty = row.get('po_buying_quantity', 0)
    po_pending = row.get('po_line_pending_invoiced_qty', 0)
    an_uninv = row['uninvoiced_quantity']
    legacy_qty = row.get('legacy_invoice_qty', 0)
    true_remaining = row.get('true_remaining_qty', an_uninv)
    
    cols[5].text(f"{po_qty:.0f}")
    cols[6].text(f"{po_pending:.0f}")
    cols[7].text(f"{an_uninv:.0f}")
    cols[8].text(f"{legacy_qty:.0f}" if legacy_qty > 0 else "-")
    cols[9].text(f"{true_remaining:.0f}")
    
    cols[10].text(row['buying_unit_cost'].split()[0][:6])
    vat_percent = row.get('vat_percent', 0)
    cols[11].text(f"{vat_percent:.0f}%")
    
    currency = row['buying_unit_cost'].split()[-1] if ' ' in str(row['buying_unit_cost']) else 'USD'
    cols[12].text(f"{row['estimated_invoice_value']:,.0f}")
    
    risk_status = []
    if row.get('po_line_is_over_delivered') == 'Y':
        risk_status.append("🔴OD")
    if row.get('po_line_is_over_invoiced') == 'Y':
        risk_status.append("🔴OI")
    if legacy_qty > 0:
        risk_status.append("⚠️LEG")
    if true_remaining < an_uninv:
        risk_status.append("⚠️ADJ")
    if po_pending < an_uninv:
        risk_status.append("⚠️EXC")
    
    cols[13].text(" ".join(risk_status) if risk_status else "✅OK")

def get_status_color(status):
    """Get status color emoji"""
    return {
        'COMPLETED': '🟢',
        'OVER_DELIVERED': '🔴',
        'PENDING': '⚪',
        'PENDING_INVOICING': '🟡',
        'PENDING_RECEIPT': '🟠',
        'IN_PROCESS': '🔵',
        'UNKNOWN_STATUS': '⚫'
    }.get(status, '⚫')

def show_invoice_preview():
    """Step 2: Invoice Preview with Enhanced Exchange Rate Handling"""
    
    if 'selected_df' not in st.session_state or st.session_state.selected_df is None:
        st.error("No data found. Please go back and select ANs.")
        if st.button("⬅️ Back to Selection"):
            st.session_state.wizard_step = 'select'
            st.rerun()
        return
    
    selected_df = st.session_state.selected_df
    
    with st.spinner("Loading invoice details..."):
        details_df = get_invoice_details(st.session_state.selected_ans)
    
    if details_df.empty:
        st.error("Could not load invoice details. Please try again.")
        if st.button("⬅️ Back to Selection"):
            st.session_state.wizard_step = 'select'
            st.rerun()
        return
    
    st.session_state.details_df = details_df
    
    po_currency_id = details_df['po_currency_id'].iloc[0] if not details_df.empty else 1
    po_currency_code = details_df['po_currency_code'].iloc[0] if not details_df.empty else 'USD'
    
    st.markdown("### 📄 Invoice Information")
    
    if 'selected_payment_term' not in st.session_state:
        unique_payment_terms_from_selected = selected_df['payment_term'].dropna().unique().tolist()
        if unique_payment_terms_from_selected:
            most_common_term = selected_df['payment_term'].mode()
            if not most_common_term.empty:
                st.session_state.selected_payment_term = most_common_term.iloc[0]
            else:
                st.session_state.selected_payment_term = unique_payment_terms_from_selected[0]
        else:
            st.session_state.selected_payment_term = 'Net 30'
    
    if 'invoice_date' not in st.session_state:
        st.session_state.invoice_date = date.today()
    
    col1, col2 = st.columns(2)
    
    with col1:
        current_advance_state = st.session_state.is_advance_payment
        
        advance_payment = st.checkbox(
            "Advance Payment Invoice",
            value=st.session_state.is_advance_payment,
            key="advance_payment_toggle",
            help="Check this for advance payment invoices (PI). This will change the invoice number suffix."
        )
        
        if advance_payment != current_advance_state:
            st.session_state.is_advance_payment = advance_payment
            st.rerun()
    
    vendor_code = selected_df['vendor_code'].iloc[0]
    vendor_id = details_df['vendor_id'].iloc[0] if not details_df.empty else None
    buyer_id = details_df['entity_id'].iloc[0] if not details_df.empty else None
    
    invoice_number = generate_invoice_number(vendor_id, buyer_id, st.session_state.is_advance_payment)
    
    with col2:
        if st.session_state.is_advance_payment:
            st.info("🔵 **Invoice Type: Advance Payment (PI)**")
        else:
            st.success("🟢 **Invoice Type: Commercial Invoice (CI)**")
    
    st.markdown("### 💱 Currency Selection")
    
    currencies_df = get_available_currencies()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"**PO Currency:** {po_currency_code}")
    
    with col2:
        currency_options = currencies_df['code'].tolist()
        currency_display = [f"{row['code']} - {row['name']}" for _, row in currencies_df.iterrows()]
        
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
        
        invoice_currency_code = selected_currency_display.split(' - ')[0]
        invoice_currency_id = currencies_df[currencies_df['code'] == invoice_currency_code]['id'].iloc[0]
    
    with col3:
        # Always calculate exchange rates (including USD rate)
        with st.spinner("Fetching exchange rates..."):
            rates = calculate_exchange_rates(po_currency_code, invoice_currency_code)
        
        # Validate rates
        rates_valid, rate_warnings = validate_exchange_rates(rates, po_currency_code, invoice_currency_code)
        
        st.markdown("**Exchange Rates:**")
        
        # Show PO to Invoice rate if different currencies
        if po_currency_code != invoice_currency_code:
            if rates['po_to_invoice_rate'] is not None:
                st.text(f"1 {po_currency_code} = {format_exchange_rate(rates['po_to_invoice_rate'])} {invoice_currency_code}")
            else:
                st.error(f"⚠️ Could not fetch {po_currency_code}/{invoice_currency_code} rate")
        else:
            st.success("✅ Same currency - No conversion needed")
        
        # Always show USD rate (important for reporting)
        if invoice_currency_code != 'USD':
            if rates['usd_exchange_rate'] is not None:
                st.text(f"1 USD = {format_exchange_rate(rates['usd_exchange_rate'])} {invoice_currency_code}")
            else:
                st.warning("⚠️ USD exchange rate not available")
        else:
            st.info("💵 Invoice currency is USD")
    
    # Show validation warnings if any
    if not rates_valid:
        st.error("❌ Required exchange rates not available. Cannot proceed with invoice.")
        for warning in rate_warnings:
            st.error(f"• {warning}")
        return
    elif rate_warnings:
        for warning in rate_warnings:
            st.warning(f"⚠️ {warning}")
    
    st.session_state.invoice_currency_code = invoice_currency_code
    st.session_state.invoice_currency_id = invoice_currency_id
    st.session_state.exchange_rates = rates
    
    unique_payment_terms_from_selected = selected_df['payment_term'].dropna().unique().tolist()
    
    term_options = {}
    
    if unique_payment_terms_from_selected:
        all_payment_terms_df = get_payment_terms()
        
        for term_name in unique_payment_terms_from_selected:
            db_match = all_payment_terms_df[all_payment_terms_df['name'] == term_name]
            
            if not db_match.empty:
                row = db_match.iloc[0]
                term_options[term_name] = {
                    'id': int(row['id']),
                    'days': int(row['days']),
                    'description': row.get('description', '')
                }
            else:
                days = calculate_days_from_term_name(term_name)
                term_id = 1
                if not details_df.empty and 'payment_term_id' in details_df.columns:
                    detail_match = details_df[details_df.get('payment_term_name', '') == term_name]
                    if not detail_match.empty:
                        term_id = int(detail_match.iloc[0]['payment_term_id'])
                
                term_options[term_name] = {
                    'id': term_id,
                    'days': days,
                    'description': f'{term_name} ({days} days)'
                }
    else:
        st.warning("⚠️ No payment terms found in selected ANs. Using default.")
        term_options = {
            'Net 30': {'id': 1, 'days': 30, 'description': 'Payment due in 30 days'}
        }
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        term_names = list(term_options.keys())
        
        default_index = 0
        if st.session_state.selected_payment_term in term_names:
            default_index = term_names.index(st.session_state.selected_payment_term)
        
        selected_term = st.selectbox(
            "Payment Terms",
            options=term_names,
            index=default_index,
            key="payment_terms_selector",
            help=f"Payment terms from selected ANs ({len(term_names)} option(s) available)"
        )
        
        if selected_term != st.session_state.selected_payment_term:
            st.session_state.selected_payment_term = selected_term
        
        if term_options[selected_term].get('description'):
            st.caption(term_options[selected_term]['description'])
    
    with col2:
        new_invoice_date = st.date_input(
            "Invoice Date",
            value=st.session_state.invoice_date,
            key="invoice_date_selector"
        )
        
        if new_invoice_date != st.session_state.invoice_date:
            st.session_state.invoice_date = new_invoice_date
    
    term_days = term_options[st.session_state.selected_payment_term]['days']
    calculated_due_date = service.calculate_due_date(st.session_state.invoice_date, term_days)
    
    with st.form("invoice_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Invoice Number", value=invoice_number, disabled=True, key="invoice_number")
            st.text_input("Invoice Date", value=str(st.session_state.invoice_date), disabled=True)
            st.text_input("Payment Terms", value=st.session_state.selected_payment_term, disabled=True)
        
        with col2:
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
            
            st.date_input(
                "Due Date",
                value=calculated_due_date,
                key="due_date",
                disabled=True,
                help=f"Auto-calculated: Invoice Date + {term_days} days ({st.session_state.selected_payment_term})"
            )
            
            email_accountant = st.checkbox(
                "Email to Accountant",
                value=False,
                key="email_to_accountant"
            )
        
        st.markdown("### 📊 Invoice Summary")
        
        if po_currency_code != invoice_currency_code:
            converted_amounts = get_invoice_amounts_in_currency(
                selected_df,
                po_currency_code,
                invoice_currency_code
            )
            
            summary_df = service.prepare_invoice_summary(selected_df)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            if converted_amounts:
                st.info(f"💱 Amounts converted from {po_currency_code} to {invoice_currency_code} at rate: {format_exchange_rate(converted_amounts['exchange_rate'])}")
                totals = converted_amounts
            else:
                st.error("❌ Cannot calculate converted amounts")
                totals = service.calculate_invoice_totals_with_vat(selected_df)
        else:
            summary_df = service.prepare_invoice_summary(selected_df)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            totals = service.calculate_invoice_totals_with_vat(selected_df)
            totals['currency'] = invoice_currency_code
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col3:
            st.markdown("**Invoice Totals**")
            st.text(f"Lines: {len(selected_df)}")
            st.text(f"Quantity: {selected_df['uninvoiced_quantity'].sum():,.2f}")
            st.text(f"Subtotal: {totals['subtotal']:,.2f} {totals['currency']}")
            st.text(f"VAT: {totals['total_vat']:,.2f} {totals['currency']}")
            st.text(f"Total: {totals['total_with_vat']:,.2f} {totals['currency']}")
        
        st.session_state.invoice_totals = totals
        
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
    
    if back_btn:
        st.session_state.wizard_step = 'select'
        st.rerun()
    
    if proceed_btn:
        if not st.session_state.is_advance_payment and not st.session_state.commercial_invoice_no:
            st.error("❌ Commercial Invoice Number is required for Commercial Invoices")
            return
        
        if invoice_currency_code == 'USD':
            usd_rate = 1.0
        else:
            usd_rate = rates.get('usd_exchange_rate', None)
        
        st.session_state.invoice_data = {
            'invoice_number': invoice_number,
            'commercial_invoice_no': st.session_state.commercial_invoice_no if not st.session_state.is_advance_payment else '',
            'invoiced_date': st.session_state.invoice_date,
            'due_date': calculated_due_date,
            'total_invoiced_amount': totals['total_with_vat'],
            'currency_id': st.session_state.invoice_currency_id,
            'usd_exchange_rate': usd_rate,
            'seller_id': details_df['vendor_id'].iloc[0] if not details_df.empty else None,
            'buyer_id': details_df['entity_id'].iloc[0] if not details_df.empty else None,
            'payment_term_id': term_options[st.session_state.selected_payment_term]['id'],
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
    """Step 3: Confirm and Submit with Duplicate Prevention"""
    
    # Check if already created
    if 'invoice_just_created' in st.session_state and st.session_state.invoice_just_created:
        st.info("✅ Invoice has been created. Redirecting...")
        time.sleep(1)
        st.session_state.wizard_step = 'select'
        st.session_state.invoice_just_created = False
        st.rerun()
        return
    
    if not st.session_state.get('invoice_data') or not st.session_state.get('details_df') is not None:
        st.error("No invoice data found. Please go back and complete the preview.")
        if st.button("⬅️ Back to Preview"):
            st.session_state.wizard_step = 'preview'
            st.rerun()
        return
    
    invoice_data = st.session_state.invoice_data
    details_df = st.session_state.details_df
    
    st.markdown("### ✅ Confirm and Submit")
    
    payment_terms_dict = service.get_payment_terms_dict()
    payment_term_name = payment_terms_dict.get(
        invoice_data['payment_term_id'], {}
    ).get('name', 'N/A')
    
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
    
    # Exchange rate information - Always show USD rate for audit purposes
    if invoice_data.get('usd_exchange_rate') is not None:
        if invoice_data['invoice_currency_code'] != 'USD':
            st.info(f"💱 USD Exchange Rate: 1 USD = {format_exchange_rate(invoice_data['usd_exchange_rate'])} {invoice_data['invoice_currency_code']}")
        else:
            st.info("💵 Invoice currency is USD (Rate: 1.0)")
    else:
        st.warning("⚠️ USD exchange rate not available for this invoice")
    
    st.markdown("### 📋 Line Items")
    
    selected_df = st.session_state.selected_df
    df_display = pd.merge(
        details_df[['arrival_detail_id', 'arrival_note_number', 'po_number', 'product_name', 'uninvoiced_quantity', 'buying_unit_cost']],
        selected_df[['can_line_id', 'vat_percent']],
        left_on='arrival_detail_id',
        right_on='can_line_id',
        how='left'
    )
    
    # Add ID column
    df_display.insert(0, 'id', range(1, len(df_display) + 1))
    
    df_display = df_display[['id', 'arrival_note_number', 'po_number', 'product_name', 
                            'uninvoiced_quantity', 'buying_unit_cost', 'vat_percent']].copy()
    
    if invoice_data['po_currency_code'] != invoice_data['invoice_currency_code']:
        df_display['converted_unit_cost'] = df_display['buying_unit_cost'].apply(
            lambda x: f"{float(x.split()[0]) * invoice_data['po_to_invoice_rate']:,.2f} {invoice_data['invoice_currency_code']}"
        )
        df_display['vat_percent'] = df_display['vat_percent'].apply(lambda x: f"{x:.0f}%")
        df_display.columns = ['ID', 'AN Number', 'PO Number', 'Product', 'Quantity', 'Original Cost', 'VAT', 'Invoice Cost']
        display_cols = ['ID', 'AN Number', 'PO Number', 'Product', 'Quantity', 'Original Cost', 'Invoice Cost', 'VAT']
    else:
        df_display['vat_percent'] = df_display['vat_percent'].apply(lambda x: f"{x:.0f}%")
        df_display.columns = ['ID', 'AN Number', 'PO Number', 'Product', 'Quantity', 'Unit Cost', 'VAT']
        display_cols = ['ID', 'AN Number', 'PO Number', 'Product', 'Quantity', 'Unit Cost', 'VAT']
    
    st.dataframe(df_display[display_cols], use_container_width=True, hide_index=True)
    
    if hasattr(st.session_state, 'invoice_totals'):
        totals = st.session_state.invoice_totals
        col1, col2, col3 = st.columns(3)
        with col3:
            st.markdown("**Final Totals**")
            st.text(f"Subtotal: {totals['subtotal']:,.2f} {totals['currency']}")
            st.text(f"VAT: {totals['total_vat']:,.2f} {totals['currency']}")
            st.text(f"Total: {totals['total_with_vat']:,.2f} {totals['currency']}")
    
    st.warning("⚠️ Please review the information above carefully. This action cannot be undone.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("⬅️ Back to Preview", use_container_width=True):
            st.session_state.wizard_step = 'preview'
            st.rerun()
    
    with col3:
        if st.button("💾 Create Invoice", type="primary", use_container_width=True):
            # Prevent duplicate submissions
            if st.session_state.invoice_creating:
                st.warning("⏳ Invoice is being created. Please wait...")
                return
            
            st.session_state.invoice_creating = True
            
            with st.spinner("Creating invoice..."):
                success, message, invoice_id = create_purchase_invoice(
                    invoice_data,
                    st.session_state.details_df,
                    st.session_state.username
                )
                
                if success:
                    # Show success briefly
                    st.success(f"✅ {message}")
                    st.balloons()
                    
                    # Store success info for display on home page
                    st.session_state.last_created_invoice = {
                        'id': invoice_id,
                        'number': invoice_data['invoice_number'],
                        'amount': invoice_data['total_invoiced_amount'],
                        'currency': invoice_data['invoice_currency_code']
                    }
                    
                    # Clear all selection data to prevent duplicates
                    for key in list(st.session_state.keys()):
                        if key not in ['username', 'authenticated', 'role', 'last_created_invoice']:
                            del st.session_state[key]
                    
                    # Reset to initial state
                    st.session_state.wizard_step = 'select'
                    st.session_state.selected_ans = []
                    st.session_state.current_page = 1
                    st.session_state.invoice_creating = False
                    st.session_state.invoice_just_created = True
                    
                    # Show redirect message
                    with st.empty():
                        for i in range(3, 0, -1):
                            st.info(f"🔄 Redirecting to home page in {i} seconds...")
                            time.sleep(1)
                    
                    st.rerun()
                else:
                    st.error(f"❌ {message}")
                    st.session_state.invoice_creating = False

if __name__ == "__main__":
    main()