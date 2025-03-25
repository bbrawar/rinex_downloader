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
        print(f"Listing files for {start_date} to {end_date}")
        file_links = []
        try:
            current_date = start_date
            while current_date <= end_date:
                year = current_date.year
                doy = current_date.timetuple().tm_yday
                doy_str = f"{doy:03d}"
                url = f"{base_url}/{year}/{doy_str}/"
                
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.find_all('a'):
                        href = link.get('href')
                        if prefixes==['all']:
                            file_links.append(url + href)
                        else:
                            if href and not href.startswith('?') and any(href.lower().startswith(prefix.lower()) for prefix in prefixes):
                                file_links.append(url + href)
                
                except requests.RequestException as e:
                    logging.error(f"Error accessing {url}: {e}")
                
                current_date += timedelta(days=1)
                
        except Exception as e:
            logging.error(f"Error in listing files: {e}")

        print(f"Found {len(file_links)} files")
        return file_links

    def download_file(self, file_url):
        file_name = file_url.split('/')[-4:]
        os.makedirs(os.path.join(self.download_dir, *file_name[:3]), exist_ok=True)
        file_path = os.path.join(self.download_dir, *file_name)
        
        try:
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024
            downloaded = 0
            
            with open(file_path, 'wb') as file:
                print(f"Downloading {file_name[-1]}")
                for data in response.iter_content(block_size):
                    file.write(data)
                    downloaded += len(data)
                    
            logging.info(f"Downloaded: {file_name}")
            return True
            
        except Exception as e:
            logging.error(f"Error downloading {file_name}: {e}")
            return False

    def create_gui(self):
        root = tk.Tk()
        root.title("RINEX File Downloader")
        root.geometry("600x400")
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Date inputs with calendar
        ttk.Label(main_frame, text="Start Date:").grid(row=0, column=0, pady=5, sticky='w')
        start_date_var = tk.StringVar()
        start_date_picker = DateEntry(
            main_frame,
            width=12,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            textvariable=start_date_var
        )
        start_date_picker.grid(row=0, column=1, pady=5, sticky='w')
        
        ttk.Label(main_frame, text="End Date:").grid(row=1, column=0, pady=5, sticky='w')
        end_date_var = tk.StringVar()
        end_date_picker = DateEntry(
            main_frame,
            width=12,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            textvariable=end_date_var
        )
        end_date_picker.grid(row=1, column=1, pady=5, sticky='w')
        
        # Prefix input
        ttk.Label(main_frame, text="Station Code \n(comma separated):").grid(row=2, column=0, pady=5)
        prefix_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=prefix_var).grid(row=2, column=1, pady=5, sticky='ew')
        
        # File type selection
        ttk.Label(main_frame, text="File Type:").grid(row=3, column=0, pady=5)
        file_type_var = tk.StringVar(value="obs")
        ttk.Combobox(main_frame, textvariable=file_type_var, values=["obs", "nav"]).grid(row=3, column=1, pady=5, sticky='ew')
        
        # Download directory selection
        ttk.Label(main_frame, text="Download Directory:").grid(row=4, column=0, pady=5)
        dir_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=dir_var).grid(row=4, column=1, pady=5, sticky='ew')
        ttk.Button(main_frame, text="Browse", command=lambda: self.select_directory(dir_var)).grid(row=4, column=2, pady=5)
        

        
        # Download button
        ttk.Button(main_frame, text="Download", 
                  command=lambda: self.start_download(
                      start_date_var.get(), end_date_var.get(),
                      prefix_var.get(), file_type_var.get(),
                      dir_var.get(), #progress_var, progress_label
                  )).grid(row=7, column=0, columnspan=3, pady=10)
        
        # Note:
        ttk.Label(main_frame, text="Note:\n 1. That station code is four characters long. \n 2. If you want to download all files, please enter 'all' in the station code field.").grid(row=8, column=0, columnspan=4, pady=5)
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        
        root.mainloop()

    def select_directory(self, dir_var):
        self.download_dir = filedialog.askdirectory()
        dir_var.set(self.download_dir)

    def start_download(self, start_date_str, end_date_str, prefix_input, file_type, download_dir):
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            prefixes = [p.strip() for p in prefix_input.split(',')] if prefix_input else []
            
            if not download_dir:
                messagebox.showerror("Error", "Please select a download directory")
                return
                
            self.download_dir = download_dir
            base_url = self.base_urls[file_type]
            
            # Get file list
            files = self.list_rinex_files(base_url, start_date, end_date, prefixes)
            
            if not files:
                messagebox.showinfo("Info", "No matching files found")
                return
                
            # Download files with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for file_url in files:
                    future = executor.submit(self.download_file, file_url)
                    futures.append(future)
                
                # Wait for all downloads to complete
                for future in futures:
                    future.result()
            
            messagebox.showinfo("Success", "All downloads completed!")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Please use YYYY-MM-DD")
        except Exception as e:
            logging.error(f"Error in download process: {e}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

if __name__ == "__main__":
    downloader = RinexDownloader()
    downloader.create_gui()
