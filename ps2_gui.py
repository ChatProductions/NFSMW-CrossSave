"""PS2 Black Edition preview window; legacy v0.5 modes stay available."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from ps2_converter import convert

def open_window(parent):
    w=tk.Toplevel(parent);w.title('CrossSave v0.7 preview | PS2 Black Edition');w.geometry('760x510')
    frame=ttk.Frame(w,padding=20);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='PS2 Black Edition / Vita import',font=('Segoe UI',17,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Experimental: offline checks passed; in-game testing required.',wraplength=700).pack(anchor='w',pady=8)
    source=tk.StringVar(value='PC');target=tk.StringVar(value='PS2');name=tk.StringVar(value='CROSS07')
    row=ttk.Frame(frame);row.pack(fill='x',pady=8)
    for title,var in [('From',source),('To',target)]:
        ttk.Label(row,text=title).pack(side='left',padx=6);ttk.Combobox(row,textvariable=var,values=['PC','GC','PS2'],state='readonly',width=12).pack(side='left')
    paths=[]
    for title in ['Source save (PC profile, GC .gci, PS2 .psu or raw PS2 profile)', 'PS2 .psu template (required only for PS2 output)']:
        ttk.Label(frame,text=title).pack(anchor='w',pady=(10,3));r=ttk.Frame(frame);r.pack(fill='x');v=tk.StringVar();paths.append(v)
        ttk.Entry(r,textvariable=v).pack(side='left',fill='x',expand=True)
        def browse(var=v):
            p=filedialog.askopenfilename(parent=w)
            if p:var.set(p)
        ttk.Button(r,text='Browse',command=browse).pack(side='left',padx=5)
    ttk.Label(frame,text='New output profile name (PS2/GC)').pack(anchor='w',pady=(12,3));ttk.Entry(frame,textvariable=name).pack(fill='x')
    ttk.Label(frame,text='PS2 output retains template settings, stock database and high scores.\nFor Vita, copy the generated .psu into ux0:data/nfsmw/save/ and start port 1.3.7+.\nRaw Vita profiles and .max archives are not supported by this preview.',wraplength=700).pack(anchor='w',pady=12)
    def run():
        try:
            src=Path(paths[0].get()).read_bytes();donor=Path(paths[1].get()).read_bytes() if target.get()=='PS2' else None
            out=convert(src,source.get(),target.get(),donor,name.get())
            suffix={ 'PC':'','GC':'.gci','PS2':'.psu'}[target.get()]
            dest=filedialog.asksaveasfilename(parent=w,initialfile=name.get()+suffix,defaultextension=suffix)
            if not dest:return
            # Exclusive write: never replace an existing profile or the input.
            with open(dest,'xb') as f:f.write(out)
            messagebox.showinfo('Conversion verified','Saved with valid checksums. Test loading, garage, career and re-saving in-game.',parent=w)
        except Exception as e:messagebox.showerror('Conversion stopped',str(e),parent=w)
    ttk.Button(frame,text='Convert and verify',command=run).pack(anchor='e')
