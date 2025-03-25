import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
from tkinter import ttk
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkcalendar import DateEntry
from tqdm import tqdm

# Set up logging
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
    
    def list_rinex_files(self, base_url, start_date, end_date, prefixes):
        logging.info(f"Listing files for {start_date} to {end_date}")
        file_links = []
        
        try:
            current_date = start_date
            while current_date <= end_date:
                year = current_date.year
                doy = current_date.timetuple().tm_yday
                url = f"{base_url}/{year}/{doy:03d}/"
                
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if prefixes == ['all'] or any(href.lower().startswith(prefix.lower()) for prefix in prefixes):
                            file_links.append(url + href)
                
                except requests.RequestException as e:
                    logging.error(f"Error accessing {url}: {e}")
                
                current_date += timedelta(days=1)
        
        except Exception as e:
            logging.error(f"Error in listing files: {e}")
        
        logging.info(f"Found {len(file_links)} files")
        return file_links

    def download_file(self, file_url):
        file_name = file_url.split('/')[-4:]
        file_path = os.path.join(self.download_dir, *file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            with open(file_path, 'wb') as file, tqdm(
                desc=f"Downloading {file_name[-1]}",
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024
            ) as bar:
                for data in response.iter_content(1024):
                    file.write(data)
                    bar.update(len(data))
            
            logging.info(f"Downloaded: {file_name[-1]}")
            return True
        
        except Exception as e:
            logging.error(f"Error downloading {file_name[-1]}: {e}")
            return False

    def create_gui(self):
        root = tk.Tk()
        root.title("RINEX File Downloader")
        root.geometry("600x400")
        
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="Start Date:").grid(row=0, column=0, pady=5, sticky='w')
        start_date_var = tk.StringVar()
        start_date_picker = DateEntry(main_frame, textvariable=start_date_var, date_pattern='yyyy-mm-dd')
        start_date_picker.grid(row=0, column=1, pady=5, sticky='w')
        
        ttk.Label(main_frame, text="End Date:").grid(row=1, column=0, pady=5, sticky='w')
        end_date_var = tk.StringVar()
        end_date_picker = DateEntry(main_frame, textvariable=end_date_var, date_pattern='yyyy-mm-dd')
        end_date_picker.grid(row=1, column=1, pady=5, sticky='w')
        
        ttk.Label(main_frame, text="Station Code (comma separated):").grid(row=2, column=0, pady=5)
        prefix_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=prefix_var).grid(row=2, column=1, pady=5, sticky='ew')
        
        ttk.Label(main_frame, text="File Type:").grid(row=3, column=0, pady=5)
        file_type_var = tk.StringVar(value="obs")
        ttk.Combobox(main_frame, textvariable=file_type_var, values=["obs", "nav"]).grid(row=3, column=1, pady=5, sticky='ew')
        
        ttk.Label(main_frame, text="Download Directory:").grid(row=4, column=0, pady=5)
        dir_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=dir_var).grid(row=4, column=1, pady=5, sticky='ew')
        ttk.Button(main_frame, text="Browse", command=lambda: self.select_directory(dir_var)).grid(row=4, column=2, pady=5)
        
        ttk.Button(main_frame, text="Download", command=lambda: self.start_download(
            start_date_var.get(), end_date_var.get(), prefix_var.get(), file_type_var.get(), dir_var.get()
        )).grid(row=5, column=0, columnspan=3, pady=10)
        
        ttk.Label(main_frame, text="Note: \n 1. Station code is four characters. \n 2. Use 'all' to download all files.").grid(row=6, column=0, columnspan=3, pady=5)
        
        main_frame.columnconfigure(1, weight=1)
        root.mainloop()

    def select_directory(self, dir_var):
        self.download_dir = filedialog.askdirectory()
        dir_var.set(self.download_dir)
    
    def start_download(self, start_date_str, end_date_str, prefix_input, file_type, download_dir):
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            prefixes = prefix_input.split(',') if prefix_input else []
            
            if not download_dir:
                messagebox.showerror("Error", "Please select a download directory")
                return
            
            self.download_dir = download_dir
            files = self.list_rinex_files(self.base_urls[file_type], start_date, end_date, prefixes)
            
            if not files:
                messagebox.showinfo("Info", "No matching files found")
                return
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                executor.map(self.download_file, files)
            
            messagebox.showinfo("Success", "All downloads completed!")
        
        except Exception as e:
            logging.error(f"Error in download process: {e}")
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    RinexDownloader().create_gui()
