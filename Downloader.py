from datetime import datetime, timezone
import os
from pathlib import Path
import threading
import time
import tkinter
import webbrowser
from PIL.ImageTk import PhotoImage
from hurry.filesize import size
from tkinter.ttk import *
from tkinter import filedialog, ttk
import psutil as psutil
import requests
import tqdm
import zipfile
import sys
import json

current_version = 'v0.6'
installer_release_url = 'https://api.github.com/repos/externoak/A32NX-installer/releases/latest'
master_prerelease_url = 'https://api.github.com/repos/flybywiresim/a32nx/releases/tags/vmaster'
latest_release_url = 'https://api.github.com/repos/flybywiresim/a32nx/releases/latest'
asset_json_name = 'asset.json'


class Request:

    cancel_check = False

    @staticmethod
    def get(url: str):
        response = requests.get(url)
        return response

    @staticmethod
    def download_file(url: str, file_name: str, progress_bar: Progressbar, response_status: ttk.Label, stable: bool):
        Request.cancel_check = False
        if stable:
            download_message = f"Downloading stable version..."
        else:
            download_message = f"Downloading development version..."
        chunk_size = 131072
        req = requests.get(url, stream=True, allow_redirects=False, headers={'Accept-Encoding': None})
        if req.status_code == 200:
            try:
                progress_bar.pack(side="top", pady=(40, 0))
                progress_bar['value'] = 0
                file_size = int(req.headers['Content-Length'])
                num_bars = int(file_size / chunk_size)
                pbar_percentage = tqdm.tqdm(total=int(file_size), bar_format='{percentage}')
                start = time.perf_counter()
                dl = 0
                with open(f'{sys.prefix}/{file_name}', 'wb') as fp:
                    response_status['text'] = download_message
                    for chunk in tqdm.tqdm(req.iter_content(chunk_size=chunk_size), total=num_bars, unit='B', desc=f'{sys.prefix}/{file_name}', disable=True):
                        fp.write(chunk)
                        dl += len(chunk)
                        response_status['text'] = f"{download_message} {round(dl // (time.perf_counter() - start) / 1600000, 3)} MB/s"
                        pbar_percentage.update(len(chunk))
                        current_percentage = round(float(str(pbar_percentage)))
                        progress_bar['value'] = current_percentage
                        style.configure('text.Horizontal.TProgressbar', text=f'{current_percentage} %')
                        progress_bar.update()
                        if Request.cancel_check:
                            fp.close()
                            break
                progress_bar.pack_forget()
                response_status['text'] = ""
            except KeyError:
                progress_bar.pack_forget()
                total_chunk_downloaded = 0
                with open(f'{sys.prefix}/{file_name}', 'wb') as fp:
                    for chunk in req.iter_content(chunk_size=chunk_size):
                        total_chunk_downloaded = total_chunk_downloaded + chunk_size
                        response_status['text'] = f"{download_message} {size(total_chunk_downloaded)}b!"
                        fp.write(chunk)
                        progress_bar.update()
                        if Request.cancel_check:
                            fp.close()
                            break
                response_status['text'] = ""
            except PermissionError:
                response_status['text'] = f"Error when downloading, permission denied. Please try and run as admin."
                response_status['background'] = "firebrick"
        elif req.status_code == 302:
            Request.download_file(url=req.headers['location'], file_name=file_name, progress_bar=progress_bar, response_status=response_status, stable=stable)
        else:
            response_status['text'] = f"Error when downloading, response code:{req.status_code}"
            response_status['background'] = "firebrick"
        progress_bar.pack_forget()

    @staticmethod
    def update_cancel():
        Request.cancel_check = True

    @staticmethod
    def open_installer_release_page_browser():
        webbrowser.open(url='https://github.com/Externoak/A32NX-installer/releases/latest')


class CreateToolTip(object):

    def __init__(self, widget, text='widget info'):
        self.waittime = 500
        self.wraplength = 180
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, _event=None):
        self.schedule()

    def leave(self, _event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        current_id = self.id
        self.id = None
        if current_id:
            self.widget.after_cancel(current_id)

    def showtip(self):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 50
        y += self.widget.winfo_rooty() + 35
        self.tw = tkinter.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = ttk.Label(self.tw, text=self.text, justify='left',
                          background="#1B1B1B", relief='solid', borderwidth=1,
                          wraplength=self.wraplength)
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()


class Application(ttk.Frame):

    def __init__(self, master=None):
        super().__init__(master)
        master.title(f'FlyByWire Downloader {current_version}')
        self.change_folder = True
        self.original_background = ""
        self.Artwork = ttk.Label(image="", borderwidth=0)
        self.photo = PhotoImage(file=f"{sys.prefix}/Image.pbm")
        self.Artwork['image'] = self.photo
        self.Artwork.photo = self.photo
        self.Artwork.pack()
        if "FlightSimulator.exe" not in (p.name() for p in psutil.process_iter()):
            self.latest_release_version = ""
            self.latest_development_update_timestamp = ""
            self.response_status = ttk.Label(text="Welcome to A32NX Mod Downloader & Installer!", wraplength=400, background="#1B1B1B", foreground="white")
            self.response_status.pack(side="top", fill=tkinter.X)
            self.update_installer_label = ttk.Label(text="", background="#1B1B1B")
            threading.Thread(target=self.check_installer_update()).start()
            self.filler_label = ttk.Label(text="", background="#1B1B1B")
            self.filler_label.pack(side="top", fill=tkinter.X)
            self.destination_folder_msg = ttk.Label(text="", background="#1B1B1B", wraplength=400)
            self.destination_folder_msg.pack(side="top", fill=tkinter.X)
            self.progress_bar = ttk.Progressbar(self, style='text.Horizontal.TProgressbar', orient="horizontal", length=200, mode="determinate")
            self.download_dev_btn = ttk.Button(self, text="Development version", width=20, style='W1.TButton', command=self.download_dev)
            self.download_stable_btn = ttk.Button(self, width=20, text="Stable version", style='W2.TButton', command=self.download_stable)
            self.browse_button = ttk.Button(self, text="", width=30, style='W3.TButton', command=self.browse_search)
            self.exit = ttk.Button(self, text="Exit", style='W4.TButton', command=self.master.destroy)
            self.exit.pack(side="bottom", pady=(30, 0), padx=(184, 184))
            self.filler_label2 = ttk.Label(text="", background="#1B1B1B")
            self.filler_label2.pack(side="bottom", fill=tkinter.X)
            self.cancel = ttk.Button(self, text="Cancel", style='W5.TButton', command=Request.update_cancel)
            root.bind_class("TButton", "<Enter>", self.on_enter)
            root.bind_class("TButton", "<Leave>", self.on_leave)
            try:
                user_cfg_path = None
                normal_steam_user_cfg_location = Path(f'{os.environ["APPDATA"]}\\Microsoft Flight Simulator\\UserCfg.opt')
                normal_msfs_store_user_cfg_location = Path(f'{os.environ["LOCALAPPDATA"]}\\Packages\\Microsoft.FlightSimulator_8wekyb3d8bbwe\\LocalCache\\UserCfg.opt')
                if normal_steam_user_cfg_location.is_file():
                    user_cfg_path = normal_steam_user_cfg_location
                elif normal_msfs_store_user_cfg_location.is_file():
                    user_cfg_path = normal_msfs_store_user_cfg_location
                else:
                    try:
                        for path in Path(Path(os.environ['APPDATA']).parent).rglob('UserCfg.opt'):
                            clean_path = path.resolve()
                            if "Flight" in str(clean_path) and str(clean_path).endswith('UserCfg.opt'):
                                user_cfg_path = path
                                break
                    except FileNotFoundError:
                        pass
                if not user_cfg_path:
                    raise IOError
                file_data = open(user_cfg_path, 'r')
                for row in file_data:
                    if "InstalledPackagesPath" in row:
                        found_installation_path = row.split('InstalledPackagesPath')[1].lstrip().rstrip().strip('"')
                        self.destination_folder = f'{found_installation_path}\\Community'
                        self.destination_folder_msg['text'] = found_installation_path
                if not found_installation_path:
                    raise IOError
                self.browse_button['text'] = "Change destination folder"
                self.browse_button.pack(side="top", pady=(20, 0))
                self.browse_search()
                file_data.close()
            except IOError:
                self.destination_folder = ""
                self.response_status['text'] = "Welcome to A32NX Mod Downloader & Installer. Could not automatically detect Community folder, please select it manually!"
                self.browse_button['text'] = "Select Community folder"
                self.browse_button.pack(side="top", pady=(20, 0))
        else:
            self.response_status = ttk.Label(text="Welcome to A32NX Mod Downloader & Installer! Please close MSFS before installing/updating the A32NX mod to avoid issues.", wraplength=400, background="firebrick", foreground="white")
            self.response_status.pack(side="top", fill=tkinter.X)
            self.exit = ttk.Button(self, text="Exit", style='W4.TButton', command=self.master.destroy)
            self.exit.pack(side="bottom", pady=(30, 0), padx=(184, 184))
        self.pack(after=self.exit.pack(side="bottom", pady=(20, 0), padx=(184, 184)))

    def get_asset_json_path(self):
        return Path(f'{self.destination_folder}\\A32NX\\{asset_json_name}')

    def browse_search(self):
        self.response_status['background'] = ""
        self.response_status.pack(side="top", fill=tkinter.X)
        if not self.change_folder or not self.destination_folder:
            previous_folder = self.destination_folder
            self.destination_folder = filedialog.askdirectory()
            if not self.destination_folder and previous_folder:
                self.destination_folder = previous_folder
        if self.destination_folder:
            self.response_status['text'] = "Welcome to A32NX Mod Downloader & Installer!"
            threading.Thread(target=self.check_if_update_available()).start()
            self.download_dev_btn.pack(side="left", pady=(20, 0), padx=(20, 0))
            self.download_stable_btn.pack(side="right", pady=(20, 0), padx=(0, 20))
            CreateToolTip(self.download_stable_btn, f"Latest available stable version: {self.latest_release_version}")
            if self.latest_development_update_timestamp:
                date, timestamp = self.latest_development_update_timestamp.split('T')
                CreateToolTip(self.download_dev_btn, f"Latest development version was updated at: {date} {timestamp}")
            msg = f'Destination folder: {self.destination_folder}'
            self.browse_button['text'] = "Change destination folder"
            self.browse_button.pack(side="top", pady=(20, 0))
            self.change_folder = False
        else:
            self.filler_label['text'] = ""
            self.filler_label['background'] = "#1B1B1B"
            self.download_dev_btn.pack_forget()
            self.download_stable_btn.pack_forget()
            msg = 'Please select an installation folder.'
            self.browse_button['text'] = "Select Community folder"
            self.change_folder = True
            self.browse_button.pack(side="top", pady=(20, 0))
        self.destination_folder_msg['text'] = msg
        self.destination_folder_msg.pack(side="top", fill=tkinter.X)
        ttk.Label(root, text="name")

    def download_zip(self, specific_url: str, stable: bool = True):
        if self.destination_folder:
            response = Request.get(specific_url)
            if response.status_code == 200:
                self.filler_label['text'] = ""
                self.filler_label['background'] = "#1B1B1B"
                self.browse_button.pack_forget()
                self.download_dev_btn.pack_forget()
                self.download_stable_btn.pack_forget()
                self.cancel.pack(side="bottom", pady=(20, 0), padx=(184, 184))
                self.exit.pack_forget()
                download_url = response.json()["assets"][0]["browser_download_url"]
                file_name = download_url.split("/")[-1]
                threading.Thread(target=Request.download_file(url=download_url, file_name=file_name, progress_bar=self.progress_bar, response_status=self.response_status, stable=stable)).start()
                if not self.response_status['text'] and not Request.cancel_check:
                    threading.Thread(target=self.unzip_file, kwargs={'file_name': file_name, 'stable': stable}).start()
                elif Request.cancel_check or "permission denied" in self.response_status['text']:
                    if not self.response_status['text']:
                        self.response_status['text'] = f"Download cancelled!"
                    self.exit.pack(side="bottom", pady=(20, 0), padx=(184, 184))
                    self.cancel.pack_forget()
                    self.browse_button.pack(side="top", pady=(20, 0))
                    self.download_dev_btn.pack(side="left", pady=(20, 0), padx=(20, 0))
                    self.download_stable_btn.pack(side="right", pady=(20, 0), padx=(0, 20))
            else:
                self.response_status['text'] = f"Error when downloading, response code: {response.status_code}"
                self.response_status['background'] = "firebrick"

    def download_stable(self):
        self.download_zip(specific_url=latest_release_url)

    def download_dev(self):
        self.download_zip(specific_url=master_prerelease_url, stable=False)

    def check_installer_update(self):
        try:
            latest_installer_version = Request.get(installer_release_url).json()['tag_name']
            if latest_installer_version != current_version:
                self.update_installer_label['text'] = f"Please update installer, new version {latest_installer_version} available!"
                self.update_installer_label['background'] = "#e85d04"
                self.update_installer_label.pack(side="top", fill=tkinter.X)
                browser_update_button = ttk.Button(self, text="New Installer version", style='W6.TButton', command=Request.open_installer_release_page_browser)
                CreateToolTip(browser_update_button, f"New available version {latest_installer_version}, click to open webpage!")
                browser_update_button.pack()
        except KeyError:
            pass

    def check_if_update_available(self):
        try:
            manifest_path = Path(f'{self.destination_folder}\\A32NX\\manifest.json')
            if manifest_path.is_file():
                manifest_file = open(manifest_path, 'r')
                manifest_version = json.load(manifest_file)["package_version"]
                self.latest_release_version = Request.get(latest_release_url).json()['tag_name'].strip("v")
                if manifest_version == self.latest_release_version and self.get_asset_json_path().is_file():
                    with open(self.get_asset_json_path()) as file:
                        asset_data = json.load(file)
                        if 'stable' in asset_data.keys():
                            self.filler_label['text'] = f"Stable version {self.latest_release_version} is up to date!"
                            self.filler_label['background'] = "green"
                            return
                        local_asset_id = asset_data['id']
                        development_github_data = Request.get(master_prerelease_url).json()
                        latest_master_asset_id = development_github_data['assets'][0]['id']
                        self.latest_development_update_timestamp = development_github_data['assets'][0]['updated_at']
                        if local_asset_id == latest_master_asset_id:
                            self.filler_label['text'] = "Development version is up to date!"
                            self.filler_label['background'] = "green"
                        else:
                            self.filler_label['text'] = "Development version is out of date, please consider updating!"
                            self.filler_label['background'] = "#e85d04"
                else:
                    self.filler_label['text'] = "A32NX version is out of date, please consider updating!"
                    self.filler_label['background'] = "#e85d04"

        except KeyError:
            self.filler_label['text'] = "Could not check for updates! Github API rate limit could be exceeded."
            self.filler_label['background'] = "#e85d04"
        except AttributeError:
            self.filler_label['text'] = "Could not check for updates, first time installing?."
            self.filler_label['background'] = "#e85d04"

    @staticmethod
    def convert_from(windows_timestamp: int) -> str:
        unix_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        windows_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        epoch_delta = unix_epoch - windows_epoch
        windows_timestamp_in_seconds = windows_timestamp / 10_000_000
        unix_timestamp = windows_timestamp_in_seconds - epoch_delta.total_seconds()
        return datetime.utcfromtimestamp(unix_timestamp).strftime('%Y-%m-%dT%H:%M:%SZ')

    def unzip_file(self, file_name: str, stable: bool):
        self.response_status['text'] = "Installing A32NX..."
        self.response_status['background'] = ""
        self.response_status.update()
        try:
            archive = zipfile.ZipFile(f'{sys.prefix}/{file_name}')
            for file in archive.namelist():
                if not os.path.isdir(file):
                    archive.extract(file, path=self.destination_folder)
            archive.close()
            if stable:
                latest_master_asset = {'stable': 'True'}
            else:
                latest_master_asset = Request.get(master_prerelease_url).json()['assets'][0]
            with open(self.get_asset_json_path(), 'w', encoding='utf-8') as f:
                # Store asset.json in A32NX folder so we can check it later to see if it is still up to date
                json.dump(latest_master_asset, f, ensure_ascii=False, indent=4)
            self.response_status['background'] = "green"
            self.response_status['text'] = "A32NX correctly installed, everything should be good to go!"
        except (zipfile.BadZipfile, OSError, KeyError) as e:
            self.response_status['background'] = "firebrick"
            self.response_status['text'] = f"Folder could not be unzipped, failed reason: {repr(e)}!"
        self.exit.pack(side="bottom", pady=(20, 0), padx=(184, 184))
        self.cancel.pack_forget()
        self.pack()

    def on_enter(self, e):
        self.original_background = ttk.Style().configure(e.widget['style'])['background']
        ttk.Style().configure(e.widget['style'], background="#506164")

    def on_leave(self, e):
        ttk.Style().configure(e.widget['style'], background=self.original_background)


if __name__ == '__main__':
    root = tkinter.Tk()
    root.resizable(False, False)
    root.iconbitmap(default=f"{sys.prefix}/icon.ico")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(root, background='#1B1B1B')
    style.configure(root, foreground='white')
    ttk.Style().configure('W1.TButton', background="#6399AE")
    ttk.Style().configure('W2.TButton', background="#00C2CB")
    ttk.Style().configure('W3.TButton', background="#545454")
    ttk.Style().configure('W4.TButton', background="#545454")
    ttk.Style().configure('W5.TButton', background="#545454")
    ttk.Style().configure('W6.TButton', background="#00C2CB")
    style.layout('text.Horizontal.TProgressbar',
                 [('Horizontal.Progressbar.trough',
                   {'children': [('Horizontal.Progressbar.pbar',
                                  {'side': 'left', 'sticky': 'ns'})],
                    'sticky': 'nswe'}),
                  ('Horizontal.Progressbar.label', {'sticky': ''})])
    style.configure('text.Horizontal.TProgressbar', text='0 %')
    style.configure('text.Horizontal.TProgressbar', background='green')
    app = Application(master=root)
    app.mainloop()
