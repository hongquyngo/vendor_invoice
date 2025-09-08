# app.py

import streamlit as st
from utils.auth import AuthManager

# Page config
st.set_page_config(
    page_title="Purchase Invoice Management",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize auth
auth = AuthManager()

def show_login_form():
    """Display the login form"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("📄 Purchase Invoice Management")
        st.markdown("---")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
            
            if submitted:
                if username and password:
                    success, user_info = auth.authenticate(username, password)
                    
                    if success:
                        auth.login(user_info)
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error(user_info.get("error", "Authentication failed"))
                else:
                    st.warning("Please enter both username and password")

def main():
    """Main application"""
    # Check authentication
    if not auth.check_session():
        show_login_form()
        return
    
    # Sidebar
    with st.sidebar:
        st.title("📄 Purchase Invoice")
        st.write(f"Welcome, **{auth.get_user_display_name()}**")
        
        st.markdown("---")
        
        # Navigation info
        st.info("👈 Select a page from the sidebar")
        
        st.markdown("---")
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True):
            auth.logout()
            st.rerun()
    
    # Main content
    st.title("Purchase Invoice Management System")
    
    # Welcome section
    st.markdown("### Welcome to Purchase Invoice Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("""
        **📝 Create Invoice**
        - Select uninvoiced Arrival Notes (AN)
        - Generate purchase invoices
        - Submit to database
        """)
    
    with col2:
        st.info("""
        **📊 Invoice History**
        - View created invoices
        - Track payment status
        - Export reports
        """)
    
    # Quick stats (placeholder)
    st.markdown("### Quick Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Pending ANs", "0", help="ANs with uninvoiced quantity")
    
    with col2:
        st.metric("Today's Invoices", "0", help="Invoices created today")
    
    with col3:
        st.metric("This Month", "0", help="Invoices this month")
    
    with col4:
        st.metric("Total Value", "$0", help="Total invoice value this month")

if __name__ == "__main__":
    main()