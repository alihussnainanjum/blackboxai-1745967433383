import time
import requests
from bs4 import BeautifulSoup
import os.path
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

class UpworkScraper:
    def __init__(self, niche, spreadsheet_id, creds_file='credentials.json', token_file='token.pickle'):
        self.niche = niche
        self.spreadsheet_id = spreadsheet_id
        self.creds_file = creds_file
        self.token_file = token_file
        self.service = self.authenticate_google_sheets()
        self.sheet_range = 'Sheet1!A1'  # Adjust if needed
        self.seen_jobs = set()

    def authenticate_google_sheets(self):
        creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_file, SCOPES)
                # Use console flow instead of local server for OAuth
                creds = flow.run_console()
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        service = build('sheets', 'v4', credentials=creds)
        return service

    def get_listings(self):
        # Construct URL for niche search on Upwork
        url = f'https://www.upwork.com/nx/jobs/search/?q={self.niche}&sort=recency'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                          ' Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch listings: Status code {response.status_code}")
            return []
        soup = BeautifulSoup(response.text, 'html.parser')
        jobs = []

        # Upwork's job cards container and structure may change, so selectors might need updates
        job_cards = soup.find_all('section', {'data-test': 'job-tile-list'})
        if not job_cards:
            # fallback to find job cards by class or other attributes
            job_cards = soup.find_all('article', class_='job-tile')

        for card in job_cards:
            try:
                title_elem = card.find('h4')
                title = title_elem.get_text(strip=True) if title_elem else 'N/A'

                link_elem = card.find('a', href=True)
                link = 'https://www.upwork.com' + link_elem['href'] if link_elem else 'N/A'

                posted_time_elem = card.find('time')
                posted_time = posted_time_elem['datetime'] if posted_time_elem else 'N/A'

                location_elem = card.find('span', {'data-test': 'client-location'})
                location = location_elem.get_text(strip=True) if location_elem else 'N/A'

                description_elem = card.find('span', {'data-test': 'job-description-text'})
                description = description_elem.get_text(strip=True) if description_elem else 'N/A'

                experience_elem = card.find('span', {'data-test': 'job-experience-level'})
                experience = experience_elem.get_text(strip=True) if experience_elem else 'N/A'

                budget_elem = card.find('span', {'data-test': 'job-budget'})
                budget = budget_elem.get_text(strip=True) if budget_elem else 'N/A'

                project_type_elem = card.find('span', {'data-test': 'job-type'})
                project_type = project_type_elem.get_text(strip=True) if project_type_elem else 'N/A'

                contract_type_elem = card.find('span', {'data-test': 'job-contract-type'})
                contract_type = contract_type_elem.get_text(strip=True) if contract_type_elem else 'N/A'

                skills_elem = card.find_all('a', {'data-test': 'skill-tag'})
                skills = ', '.join([skill.get_text(strip=True) for skill in skills_elem]) if skills_elem else 'N/A'

                activity_elem = card.find('span', {'data-test': 'job-activity'})
                activity = activity_elem.get_text(strip=True) if activity_elem else 'N/A'

                client_info_elem = card.find('div', {'data-test': 'client-info'})
                client_info = client_info_elem.get_text(strip=True) if client_info_elem else 'N/A'

                job_id = link  # Using link as unique identifier

                if job_id not in self.seen_jobs:
                    jobs.append([
                        title, posted_time, location, description, experience,
                        budget, project_type, contract_type, skills, activity, client_info, link
                    ])
                    self.seen_jobs.add(job_id)
            except Exception as e:
                print(f"Error parsing a job card: {e}")
                continue
        return jobs

    def append_to_sheet(self, jobs):
        if not jobs:
            print("No new jobs to add.")
            return
        body = {
            'values': jobs
        }
        result = self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=self.sheet_range,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        print(f"{result.get('updates').get('updatedRows')} rows appended.")

    def run(self, delay=300):
        print(f"Starting Upwork scraper for niche: {self.niche}")
        while True:
            jobs = self.get_listings()
            self.append_to_sheet(jobs)
            print(f"Sleeping for {delay} seconds...")
            time.sleep(delay)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Upwork scraper to Google Sheets')
    parser.add_argument('--niche', required=True, help='Niche/category to scrape')
    parser.add_argument('--sheet_id', required=True, help='Google Sheet ID to append data')
    parser.add_argument('--delay', type=int, default=300, help='Delay between scrapes in seconds')
    args = parser.parse_args()

    scraper = UpworkScraper(args.niche, args.sheet_id)
    scraper.run(args.delay)
