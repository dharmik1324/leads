import argparse
import pandas as pd
from scraper import scrape_maps_leads
from google_sheets import upload_leads_to_google_sheet

def main():
    parser = argparse.ArgumentParser(description="Google Maps Lead Scraper Agent (Website-less Businesses)")
    parser.add_argument("--query", type=str, required=True, help="Google Maps search query (e.g. 'plumbers in Dallas')")
    parser.add_argument("--limit", type=int, default=20, help="Max results to scan from maps (default: 20)")
    parser.add_argument("--output", type=str, default="leads.csv", help="Output CSV filename (default: leads.csv)")
    parser.add_argument("--gsheet-name", type=str, default=None, help="Google Sheet name to upload results to (e.g. 'My Leads')")
    parser.add_argument("--gsheet-sheet", type=str, default="Sheet1", help="Worksheet name inside Google Sheet (default: Sheet1)")
    parser.add_argument("--gsheet-creds", type=str, default="credentials.json", help="Path to Google Service Account JSON credentials (default: credentials.json)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Starting Google Maps Lead Scraper Agent")
    print(f"Query:  {args.query}")
    print(f"Limit:  {args.limit}")
    print(f"Output: {args.output}")
    if args.gsheet_name:
        print(f"GSheet: {args.gsheet_name} (Worksheet: {args.gsheet_sheet})")
    print("=" * 60)
    
    leads = scrape_maps_leads(args.query, max_results=args.limit, log_callback=print)
    
    if leads:
        df = pd.DataFrame(leads)
        df.to_csv(args.output, index=False)
        print("=" * 60)
        print(f"Scraping complete! Saved {len(leads)} leads to '{args.output}'")
        
        if args.gsheet_name:
            print("=" * 60)
            print("Uploading results to Google Sheets...")
            upload_leads_to_google_sheet(
                df=df,
                spreadsheet_name=args.gsheet_name,
                credentials_path=args.gsheet_creds,
                sheet_name=args.gsheet_sheet,
                log_callback=print
            )
        print("=" * 60)
    else:
        print("=" * 60)
        print("Scraping complete. No leads found that meet the 'No Website' criteria.")
        print("=" * 60)

if __name__ == "__main__":
    main()

