import gspread
import os

def upload_leads_to_google_sheet(df, spreadsheet_name, credentials_path="credentials.json", sheet_name="Sheet1", log_callback=print):
    """
    Authenticate via Service Account JSON and upload a pandas DataFrame
    to the specified Google Sheet.
    """
    if df is None or df.empty:
        log_callback("No data to upload to Google Sheets.")
        return False
        
    if not os.path.exists(credentials_path):
        log_callback(f"⚠️ Error: Credentials file '{credentials_path}' not found.")
        log_callback("Please place your Google Service Account 'credentials.json' in the project directory.")
        log_callback("Make sure you share your Google Sheet with the client_email address listed in the credentials JSON.")
        return False
        
    try:
        log_callback(f"Connecting to Google Sheets using credentials: '{credentials_path}'...")
        gc = gspread.service_account(filename=credentials_path)
        
        log_callback(f"Opening spreadsheet: '{spreadsheet_name}'...")
        try:
            sh = gc.open(spreadsheet_name)
        except gspread.exceptions.SpreadsheetNotFound:
            log_callback(f"⚠️ Error: Spreadsheet '{spreadsheet_name}' not found.")
            log_callback("Make sure you created the Google Sheet and shared it with the Service Account email address:")
            try:
                # Try to print the service account email for easier user sharing
                import json
                with open(credentials_path, 'r') as f:
                    creds = json.load(f)
                    log_callback(f"👉 Email to share sheet with: {creds.get('client_email')}")
            except Exception:
                pass
            return False
            
        # Try to find or create the worksheet
        try:
            worksheet = sh.worksheet(sheet_name)
            log_callback(f"Found worksheet: '{sheet_name}'. Clearing old content...")
        except gspread.exceptions.WorksheetNotFound:
            log_callback(f"Worksheet '{sheet_name}' not found. Creating a new one...")
            worksheet = sh.add_worksheet(title=sheet_name, rows="100", cols="20")
            
        # Clear old content
        worksheet.clear()
        
        # Prepare content (headers + rows)
        data = [df.columns.values.tolist()] + df.values.tolist()
        
        # Write to sheet starting from A1
        log_callback("Writing leads to Google Sheet...")
        # In newer gspread versions, worksheet.update() accepts lists of lists directly with range
        worksheet.update(values=data, range_name="A1")
        
        log_callback("✨ Successfully updated Google Sheet!")
        return True
    except Exception as e:
        log_callback(f"❌ Failed to write to Google Sheets: {e}")
        return False
