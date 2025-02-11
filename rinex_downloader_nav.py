import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import simpledialog, messagebox

def list_rinex_files(base_url, start_date, end_date, prefixes):
    file_links = []
    try:
        current_date = start_date
        while current_date <= end_date:
            year = current_date.year
            doy = current_date.timetuple().tm_yday
            doy_str = f"{doy:03d}"
            url = f"{base_url}/{year}/{doy_str}/"
            response = requests.get(url)
            if response.status_code != 200:
                current_date += timedelta(days=1)
                continue
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and not href.startswith('?') and any(href.lower().startswith(prefix.lower()) for prefix in prefixes):
                    file_links.append(url + href)
            
            current_date += timedelta(days=1)
    except requests.RequestException as e:
        print(f"Error accessing {base_url}: {e}")
    
    return file_links

def download_files(file_links):
    for file_url in file_links:
        file_name = file_url.split('/')[-1]
        try:
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            with open(file_name, 'wb') as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            print(f"Downloaded: {file_name}")
        except requests.RequestException as e:
            print(f"Error downloading {file_name}: {e}")

def get_user_input():
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    
    start_date_str = simpledialog.askstring("Input", "Enter Start Date (YYYY-MM-DD):")
    end_date_str = simpledialog.askstring("Input", "Enter End Date (YYYY-MM-DD):")
    prefix_input = simpledialog.askstring("Input", "Enter prefixes (comma separated):")
    
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        prefixes = [p.strip() for p in prefix_input.split(',')] if prefix_input else []
        return start_date, end_date, prefixes
    except ValueError:
        messagebox.showerror("Error", "Invalid date format. Please enter dates as YYYY-MM-DD.")
        return None, None, None

if __name__ == "__main__":
    base_url = "http://garner.ucsd.edu/pub/nav"
    
    start_date, end_date, prefixes = get_user_input()
    
    if not start_date or not end_date or not prefixes:
        messagebox.showerror("Error", "Invalid input provided.")
    else:
        files = list_rinex_files(base_url, start_date, end_date, prefixes)
        
        if files:
            print("Downloading files:")
            download_files(files)
        else:
            messagebox.showinfo("Info", "No matching files found or unable to access the directories.")
