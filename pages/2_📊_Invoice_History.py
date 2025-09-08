# pages/2_📊_Invoice_History.py

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import io

# Import utils
from utils.auth import AuthManager
from utils.invoice_data import get_recent_invoices
from utils.invoice_service import InvoiceService

# Page config
st.set_page_config(
    page_title="Invoice History",
    page_icon="📊",
    layout="wide"
)

# Initialize
auth = AuthManager()
auth.require_auth()
service = InvoiceService()

def main():
    st.title("📊 Purchase Invoice History")
    
    # Filters
    with st.expander("🔍 Search Filters", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_filter = st.selectbox(
                "Date Range",
                ["Last 7 days", "Last 30 days", "Last 90 days", "This Month", "Custom"],
                key="date_filter"
            )
            
            if date_filter == "Custom":
                date_from = st.date_input("From Date", key="custom_from")
                date_to = st.date_input("To Date", key="custom_to")
        
        with col2:
            invoice_search = st.text_input(
                "Invoice Number",
                placeholder="Search invoice number...",
                key="invoice_search"
            )
            
            vendor_search = st.text_input(
                "Vendor",
                placeholder="Search vendor...",
                key="vendor_search"
            )
        
        with col3:
            creator_search = st.text_input(
                "Created By",
                placeholder="Search creator...",
                key="creator_search"
            )
            
            limit = st.number_input(
                "Max Records",
                min_value=10,
                max_value=500,
                value=100,
                step=50,
                key="record_limit"
            )
    
    # Get data
    df = get_recent_invoices(limit=int(limit))
    
    if df.empty:
        st.info("No invoices found.")
        return
    
    # Apply filters
    if invoice_search:
        df = df[df['invoice_number'].str.contains(invoice_search, case=False, na=False)]
    
    if vendor_search:
        df = df[df['vendor'].str.contains(vendor_search, case=False, na=False)]
    
    if creator_search:
        df = df[df['created_by'].str.contains(creator_search, case=False, na=False)]
    
    # Date filtering
    if date_filter != "Custom":
        today = pd.Timestamp.now()
        if date_filter == "Last 7 days":
            date_threshold = today - timedelta(days=7)
        elif date_filter == "Last 30 days":
            date_threshold = today - timedelta(days=30)
        elif date_filter == "Last 90 days":
            date_threshold = today - timedelta(days=90)
        elif date_filter == "This Month":
            date_threshold = today.replace(day=1)
        
        if 'date_threshold' in locals():
            df = df[df['created_date'] >= date_threshold]
    
    # Summary metrics
    st.markdown("### 📈 Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Invoices", len(df))
    
    with col2:
        total_value = df['total_invoiced_amount'].sum()
        st.metric("Total Value", f"${total_value:,.2f}")
    
    with col3:
        unique_vendors = df['vendor'].nunique()
        st.metric("Vendors", unique_vendors)
    
    with col4:
        avg_value = df['total_invoiced_amount'].mean() if len(df) > 0 else 0
        st.metric("Avg Invoice Value", f"${avg_value:,.2f}")
    
    # Invoice table
    st.markdown("### 📋 Invoice List")
    
    # Format display
    df_display = df.copy()
    
    # Format dates
    if 'invoiced_date' in df_display.columns:
        df_display['invoiced_date'] = pd.to_datetime(df_display['invoiced_date']).dt.strftime('%Y-%m-%d')
    if 'due_date' in df_display.columns:
        df_display['due_date'] = pd.to_datetime(df_display['due_date']).dt.strftime('%Y-%m-%d')
    if 'created_date' in df_display.columns:
        df_display['created_date'] = pd.to_datetime(df_display['created_date']).dt.strftime('%Y-%m-%d %H:%M')
    
    # Format amount
    df_display['total_amount'] = df_display.apply(
        lambda row: f"{row['total_invoiced_amount']:,.2f} {row['currency']}", axis=1
    )
    
    # Select columns to display
    display_columns = [
        'invoice_number', 'invoiced_date', 'vendor', 
        'total_amount', 'line_count', 'po_count',
        'due_date', 'created_by', 'created_date'
    ]
    
    # Rename columns for display
    column_mapping = {
        'invoice_number': 'Invoice #',
        'invoiced_date': 'Invoice Date',
        'vendor': 'Vendor',
        'total_amount': 'Amount',
        'line_count': 'Lines',
        'po_count': 'POs',
        'due_date': 'Due Date',
        'created_by': 'Created By',
        'created_date': 'Created'
    }
    
    df_display = df_display[display_columns].rename(columns=column_mapping)
    
    # Display as dataframe with selection
    selected = st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        selection_mode="multi-row",
        on_select="rerun"
    )
    
    # Export options
    st.markdown("### 📥 Export Options")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export to Excel
        if st.button("📊 Export to Excel", use_container_width=True):
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_display.to_excel(writer, sheet_name='Invoices', index=False)
            
            st.download_button(
                label="Download Excel File",
                data=buffer.getvalue(),
                file_name=f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col2:
        # Export to CSV
        if st.button("📄 Export to CSV", use_container_width=True):
            csv = df_display.to_csv(index=False)
            st.download_button(
                label="Download CSV File",
                data=csv,
                file_name=f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col3:
        # Selected rows info
        if selected and selected.selection:
            selected_count = len(selected.selection["rows"])
            st.info(f"Selected {selected_count} invoice(s)")

if __name__ == "__main__":
    main()