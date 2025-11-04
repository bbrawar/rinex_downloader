import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkcalendar import DateEntry
from tqdm import tqdm

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rinex_downloader.log'),
        logging.StreamHandler()
    ]
)

class RinexDownloader:
    def __init__(self):
        self.base_urls = {
            "obs": "http://garner.ucsd.edu/pub/rinex",
            "nav": "http://garner.ucsd.edu/pub/nav"
        }
        self.download_dir = ""
        self.session = self._init_session()

    def _init_session(self):
        """Initialize a resilient HTTP session with retry strategy."""
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def list_rinex_files(self, base_url, start_date, end_date, prefixes):
        logging.info(f"Listing RINEX files between {start_date.date()} and {end_date.date()}")
        file_links = []
        current_date = start_date

        while current_date <= end_date:
            year = current_date.year
            doy = current_date.timetuple().tm_yday
            url = f"{base_url}/{year}/{doy:03d}/"
            try:
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if prefixes == ['all'] or any(href.lower().startswith(p.strip().lower()) for p in prefixes):
                        file_links.append(url + href)
            except requests.RequestException as e:
                logging.warning(f"Skipping {url}: {e}")
            current_date += timedelta(days=1)

        logging.info(f"Found {len(file_links)} files to download.")
        return file_links

    def download_file(self, file_url):
        """Download one file and return success status."""
        file_parts = file_url.split('/')[-4:]
        file_path = Path(self.download_dir, *file_parts)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self.session.get(file_url, stream=True, timeout=15) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                with open(file_path, 'wb') as f, tqdm(
                    total=total_size, unit='B', unit_scale=True, desc=file_path.name, leave=False
                ) as bar:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            bar.update(len(chunk))
            return True
        except Exception as e:
            logging.error(f"Failed: {file_url} -> {e}")
            return False

    def create_gui(self):
        root = tk.Tk()
        root.title("RINEX File Downloader")
        root.geometry("650x450")

        frame = ttk.Frame(root, padding="12")
        frame.pack(fill=tk.BOTH, expand=True)

        # Inputs
        ttk.Label(frame, text="Start Date:").grid(row=0, column=0, sticky='w')
        start_date = tk.StringVar()
        DateEntry(frame, textvariable=start_date, date_pattern='yyyy-mm-dd').grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="End Date:").grid(row=1, column=0, sticky='w')
        end_date = tk.StringVar()
        DateEntry(frame, textvariable=end_date, date_pattern='yyyy-mm-dd').grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Station Codes (comma-separated or 'all'):").grid(row=2, column=0, sticky='w')
        prefixes = tk.StringVar()
        ttk.Entry(frame, textvariable=prefixes).grid(row=2, column=1, sticky='ew', pady=5)

        ttk.Label(frame, text="File Type:").grid(row=3, column=0, sticky='w')
        file_type = tk.StringVar(value="obs")
        ttk.Combobox(frame, textvariable=file_type, values=["obs", "nav"], state="readonly").grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Download Directory:").grid(row=4, column=0, sticky='w')
        dir_var = tk.StringVar()
        ttk.Entry(frame, textvariable=dir_var).grid(row=4, column=1, sticky='ew', pady=5)
        ttk.Button(frame, text="Browse", command=lambda: self.select_directory(dir_var)).grid(row=4, column=2, padx=5)

        # Progress bar and status
        progress = ttk.Progressbar(frame, length=400, mode='determinate')
        progress.grid(row=6, column=0, columnspan=3, pady=10)
        status_label = ttk.Label(frame, text="Ready.")
        status_label.grid(row=7, column=0, columnspan=3)

        # Download button
        ttk.Button(frame, text="Start Download", command=lambda: self.start_download_gui(
            start_date.get(), end_date.get(), prefixes.get(), file_type.get(), dir_var.get(),
            progress, status_label, root
        )).grid(row=5, column=0, columnspan=3, pady=15)

        frame.columnconfigure(1, weight=1)
        root.mainloop()

    def select_directory(self, dir_var):
        self.download_dir = filedialog.askdirectory()
        dir_var.set(self.download_dir)

    def start_download_gui(self, start, end, prefix, ftype, out_dir, progress, status_label, root):
        """Wrapper for threaded GUI execution."""
        if not out_dir:
            messagebox.showerror("Error", "Please select a download directory")
            return
        self.download_dir = out_dir

        def task():
            try:
                status_label.config(text="Fetching file list...")
                start_date = datetime.strptime(start, "%Y-%m-%d")
                end_date = datetime.strptime(end, "%Y-%m-%d")
                prefixes = prefix.split(',') if prefix else ['all']

                files = self.list_rinex_files(self.base_urls[ftype], start_date, end_date, prefixes)
                if not files:
                    messagebox.showinfo("Info", "No matching files found.")
                    status_label.config(text="No files found.")
                    return

                progress['maximum'] = len(files)
                progress['value'] = 0
                success, fail = 0, 0

                with ThreadPoolExecutor(max_workers=3) as exe:
                    futures = {exe.submit(self.download_file, url): url for url in files}
                    for i, future in enumerate(as_completed(futures)):
                        if future.result():
                            success += 1
                        else:
                            fail += 1
                        progress['value'] = i + 1
                        status_label.config(text=f"Progress: {i+1}/{len(files)}")

                messagebox.showinfo("Download Complete", f"✅ Successful: {success}\n❌ Failed: {fail}")
                status_label.config(text="Download finished.")
            except Exception as e:
                logging.error(f"Error in GUI download: {e}")
                messagebox.showerror("Error", str(e))

        # Run in background
        root.after(100, lambda: ThreadPoolExecutor(max_workers=1).submit(task))

if __name__ == "__main__":
    RinexDownloader().create_gui()
