import os
import tkinter as tk
from tkinter import filedialog

def rename_files(folder_path, series_name, episode_prefix, file_extension):
    file_list = sorted([f for f in os.listdir(folder_path) if f.endswith(file_extension)])
    for index, file_name in enumerate(file_list):
        new_name = f'{series_name}{episode_prefix}{index+1:02d}.{file_extension}'
        src = os.path.join(folder_path, file_name)
        dst = os.path.join(folder_path, new_name)
        os.rename(src, dst)

def select_folder(folder_entry):
    folder_path = filedialog.askdirectory()
    folder_entry.delete(0, tk.END)
    folder_entry.insert(tk.END, folder_path)

def rename_files_gui():
    window = tk.Tk()
    window.title("文件重命名")
    
    folder_label = tk.Label(window, text="文件夹路径:")
    folder_label.pack()
    
    folder_entry = tk.Entry(window)
    folder_entry.pack()
    
    folder_button = tk.Button(window, text="选择文件夹", command=lambda: select_folder(folder_entry))
    folder_button.pack()
    
    series_label = tk.Label(window, text="剧名:")
    series_label.pack()
    
    series_entry = tk.Entry(window)
    series_entry.pack()

    episode_prefix_label = tk.Label(window, text="集数格式（-S01E,-E）:")
    episode_prefix_label.pack()

    episode_prefix_entry = tk.Entry(window)
    episode_prefix_entry.pack()

    file_extension_label = tk.Label(window, text="文件后缀(mp4,nfo):")
    file_extension_label.pack()

    file_extension_entry = tk.Entry(window)
    file_extension_entry.pack()
    
    rename_button = tk.Button(window, text="批量重命名", command=lambda: rename_files(folder_entry.get(), series_entry.get(), episode_prefix_entry.get(), file_extension_entry.get()))
    rename_button.pack()

    notice_label = tk.Label(window, text="PS：确保你的文件能修改文件扩展名", fg="red")
    notice_label.pack(side=tk.BOTTOM)
    
    window.mainloop()

rename_files_gui()
