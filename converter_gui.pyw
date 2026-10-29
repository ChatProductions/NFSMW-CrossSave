"""NFSMW CrossSave v0.5: PC / GameCube save conversion and experimental region transfer."""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

from converter_core import (
    ConversionError, gc_to_pc, pc_to_gc, gc_to_gc, describe, profile_name,
    parse_pc, parse_gci, gamecube_game_id, GAMECUBE_REGIONS, DEFAULT_GAME_ID,
)

APP_NAME = 'NFSMW CrossSave'
APP_VERSION = '0.7 preview'
BG = '#f2f5f9'
INK = '#172a45'
REGION_LABELS = {f'{label}  |  {game_id}': game_id for game_id, label in GAMECUBE_REGIONS.items()}


class CrossSaveApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'{APP_NAME}  |  v{APP_VERSION}')
        self.geometry('930x840')
        self.minsize(835, 790)
        self.configure(bg=BG)
        try:
            self.iconbitmap(str(Path(__file__).resolve().parent / 'assets' / 'crosssave.ico'))
        except (tk.TclError, OSError):
            pass
        self._style()
        self.gc_in = tk.StringVar()
        self.pc_in = tk.StringVar()
        self.pc_out = tk.StringVar()
        self.gc_out = tk.StringVar()
        self.gc_gc_out = tk.StringVar()
        self.pc_gc_profile_name = tk.StringVar()
        self.gc_gc_profile_name = tk.StringVar()
        self.region_choice = tk.StringVar(value=next(iter(REGION_LABELS)))
        self.source_region = tk.StringVar(value='Source GameCube edition: detected when inspecting a save')
        self.use_template = tk.BooleanVar(value=False)
        self.template_path = tk.StringVar()
        self.cash_enabled = tk.BooleanVar(value=False)
        self.cash_value = tk.StringVar(value='250000')
        self.direction = 'gc_pc'
        self._last_output: Path | None = None
        self._build()
        from ps2_gui import open_window
        menu = tk.Menu(self)
        menu.add_command(label="PS2 Black Edition / Vita (preview)", command=lambda: open_window(self))
        self.config(menu=menu)
        self._log('Ready. No blank destination-platform saves required.')
        self._log('USA PC <-> GameCube conversion has passed in-game tests on supplied saves.')
        self._log('European and Japanese edition conversions are experimental pending in-game tests.')

    def _style(self):
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=INK, font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI Semibold', 20), foreground='#102c52')
        style.configure('Subtitle.TLabel', font=('Segoe UI', 10), foreground='#526781')
        style.configure('Section.TLabel', font=('Segoe UI Semibold', 11), foreground='#102c52')
        style.configure('Form.TFrame', background='#ffffff')
        style.configure('FormTitle.TLabel', background='#ffffff', foreground='#102c52', font=('Segoe UI Semibold', 11))
        style.configure('FormHelp.TLabel', background='#ffffff', foreground='#526781', font=('Segoe UI', 10))
        style.configure('TEntry', padding=4)
        style.configure('TCombobox', padding=4)
        style.configure('TButton', font=('Segoe UI', 10), padding=(10, 7))
        style.configure('Primary.TButton', font=('Segoe UI Semibold', 10), padding=(15, 7), background='#195fa7', foreground='white')
        style.map('Primary.TButton', background=[('active', '#114a86')], foreground=[('disabled', '#c8d0da')])
        style.configure('TCheckbutton', background=BG, foreground=INK)

    def _build(self):
        wrapper = ttk.Frame(self, padding=(24, 12, 24, 8))
        wrapper.pack(fill='both', expand=True)
        ttk.Label(wrapper, text='NFSMW CrossSave', style='Title.TLabel').pack(anchor='w')
        ttk.Label(wrapper, text='Need for Speed: Most Wanted (2005)  •  PC ↔ GameCube + PS2 preview  •  v0.7', style='Subtitle.TLabel').pack(anchor='w', pady=(0, 8))

        notice = tk.Frame(wrapper, bg='#e8f2fc', highlightbackground='#c9dff5', highlightthickness=1)
        notice.pack(fill='x', pady=(0, 8))
        tk.Label(notice, text='✓  Donor-free conversion', bg='#e8f2fc', fg='#14538c', font=('Segoe UI Semibold', 11), padx=14, pady=5).pack(side='left')
        tk.Label(notice, text='Five GameCube editions • automatic detection • original files unchanged', bg='#e8f2fc', fg='#355d81', font=('Segoe UI', 10), padx=5).pack(side='left')

        nav = tk.Frame(wrapper, bg=BG)
        nav.pack(fill='x')
        self.nav_buttons = {}
        self.nav_bars = {}
        for key, title in [('gc_pc', 'GameCube → PC'), ('pc_gc', 'PC → GameCube'), ('gc_gc', 'GameCube → GameCube')]:
            cell = tk.Frame(nav, bg=BG)
            cell.pack(side='left', fill='y', padx=(0, 4))
            btn = tk.Button(cell, text=title, relief='flat', bd=0,
                            font=('Segoe UI Semibold', 10), padx=17, pady=9,
                            cursor='hand2', command=lambda k=key: self._set_direction(k))
            btn.pack(fill='x')
            bar = tk.Frame(cell, height=3)
            bar.pack(fill='x')
            self.nav_buttons[key] = btn
            self.nav_bars[key] = bar

        panel = tk.Frame(wrapper, bg='white', highlightbackground='#c8d5e3',
                         highlightthickness=1, height=390)
        panel.pack(fill='x')
        panel.pack_propagate(False)
        form = ttk.Frame(panel, padding=(16, 11, 16, 10), style='Form.TFrame')
        form.pack(fill='both', expand=True)

        self.source_label = ttk.Label(form, text='', style='FormTitle.TLabel')
        self.source_label.pack(anchor='w', pady=(0, 3))
        line = ttk.Frame(form, style='Form.TFrame')
        line.pack(fill='x', pady=(0, 7))
        self.source_entry = ttk.Entry(line)
        self.source_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        ttk.Button(line, text='Browse…', command=self._browse_source).pack(side='right')

        ttk.Label(form, text='2. Output folder (optional; defaults beside source)', style='FormTitle.TLabel').pack(anchor='w', pady=(0, 3))
        line = ttk.Frame(form, style='Form.TFrame')
        line.pack(fill='x', pady=(0, 8))
        self.output_entry = ttk.Entry(line)
        self.output_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        ttk.Button(line, text='Browse…', command=self._browse_output).pack(side='right')

        self.gc_region_group = ttk.Frame(form, style='Form.TFrame')
        ttk.Label(self.gc_region_group, text='3. Destination GameCube edition', style='FormTitle.TLabel').pack(anchor='w', pady=(0, 3))
        combo = ttk.Combobox(self.gc_region_group, state='readonly', textvariable=self.region_choice,
                             values=list(REGION_LABELS), width=48)
        combo.pack(anchor='w', pady=(0, 5))

        self.gc_name_group = ttk.Frame(form, style='Form.TFrame')
        self.gc_name_label = ttk.Label(self.gc_name_group, text='4. Internal GameCube profile name (optional)', style='FormTitle.TLabel')
        self.gc_name_label.pack(anchor='w', pady=(0, 3))
        self.gc_name_entry = ttk.Entry(self.gc_name_group)
        self.gc_name_entry.pack(fill='x', pady=(0, 5))
        self.gc_name_help = ttk.Label(self.gc_name_group, text='', style='FormHelp.TLabel', wraplength=830)
        self.gc_name_help.pack(anchor='w')

        self.pc_help_group = ttk.Frame(form, style='Form.TFrame')
        ttk.Label(self.pc_help_group, text='3. Install the converted PC save', style='FormTitle.TLabel').pack(anchor='w', pady=(0, 5))
        ttk.Label(self.pc_help_group,
                  text='Creates PROFILE\\PROFILE. Copy that folder into Documents\\NFS Most Wanted\\. Back up any existing profile first.',
                  style='FormHelp.TLabel', wraplength=830).pack(anchor='w')

        self.source_region_label = ttk.Label(form, textvariable=self.source_region, style='FormHelp.TLabel', wraplength=830)

        advanced = ttk.Frame(wrapper)
        advanced.pack(fill='x', pady=(6, 0))
        self.advanced_checkbox = ttk.Checkbutton(advanced,
                        text='Advanced: use my own destination-platform template (optional)',
                        variable=self.use_template, command=self._toggle_template)
        self.advanced_checkbox.pack(anchor='w')
        self.template_row = ttk.Frame(advanced)
        self.template_label = ttk.Label(self.template_row, text='', style='Subtitle.TLabel')
        self.template_label.pack(anchor='w', pady=(7, 3))
        line = ttk.Frame(self.template_row)
        line.pack(fill='x')
        ttk.Entry(line, textvariable=self.template_path).pack(side='left', fill='x', expand=True, padx=(0, 8))
        ttk.Button(line, text='Browse…', command=self._browse_template).pack(side='right')
        self._set_direction('gc_pc')

        options = ttk.Frame(wrapper)
        options.pack(fill='x', pady=(7, 8))
        ttk.Checkbutton(options, text='Set cash to:', variable=self.cash_enabled).pack(side='left', padx=(0, 10))
        ttk.Entry(options, textvariable=self.cash_value, width=14).pack(side='left')
        ttk.Label(options, text='Unchecked = preserve the original amount', style='Subtitle.TLabel').pack(side='left', padx=12)

        buttons = ttk.Frame(wrapper)
        buttons.pack(fill='x', pady=(0, 10))
        ttk.Button(buttons, text='Inspect save', command=self.inspect).pack(side='left')
        self.open_button = ttk.Button(buttons, text='Open output folder', command=self.open_output, state='disabled')
        self.open_button.pack(side='left', padx=(8, 0))
        ttk.Button(buttons, text='Convert and verify', style='Primary.TButton', command=self.convert).pack(side='right')

        ttk.Label(wrapper, text='Activity log', style='Section.TLabel').pack(anchor='w')
        logbox = ttk.Frame(wrapper)
        logbox.pack(fill='both', expand=True, pady=(5, 5))
        self.log = tk.Text(logbox, wrap='word', height=4, font=('Consolas', 9),
                           bg='white', fg='#18304b', relief='solid', borderwidth=1, padx=10, pady=10)
        scroll = ttk.Scrollbar(logbox, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.log.configure(state='disabled')
        ttk.Label(wrapper,
                  text='USA conversions tested in-game. Cross-region conversion is experimental until tested on matching regional editions.',
                  style='Subtitle.TLabel', wraplength=880).pack(anchor='w')

    def _selected_game_id(self):
        label = self.region_choice.get()
        if label not in REGION_LABELS:
            raise ConversionError('Select a supported destination GameCube edition.')
        return REGION_LABELS[label]

    def _set_direction(self, direction):
        self.direction = direction
        for key, button in self.nav_buttons.items():
            active = key == direction
            button.configure(bg='#ffffff' if active else '#e3eaf3',
                             fg='#13589c' if active else '#415873',
                             activebackground='#ffffff' if active else '#d8e4f1',
                             activeforeground='#13589c', relief='flat')
            self.nav_bars[key].configure(bg='#1963ac' if active else '#bdcbda')
        self.source_label.configure(text=('1. PC save (extensionless profile file)' if direction == 'pc_gc'
                                          else '1. GameCube save (.gci)'))
        self.source_entry.configure(textvariable=self.pc_in if direction == 'pc_gc' else self.gc_in)
        out = {'gc_pc': self.pc_out, 'pc_gc': self.gc_out, 'gc_gc': self.gc_gc_out}[direction]
        self.output_entry.configure(textvariable=out)
        for frame in (self.gc_region_group, self.gc_name_group, self.pc_help_group, self.source_region_label):
            frame.pack_forget()
        if direction == 'gc_pc':
            self.pc_help_group.pack(fill='x')
            self.source_region_label.pack(anchor='w', pady=(8, 0))
        else:
            if direction == 'gc_gc':
                self.source_region_label.pack(anchor='w', pady=(0, 8))
            self.gc_region_group.pack(fill='x')
            self.gc_name_group.pack(fill='x')
            self.gc_name_entry.configure(textvariable=self.pc_gc_profile_name if direction == 'pc_gc' else self.gc_gc_profile_name)
            self.gc_name_help.configure(text=(
                'Blank adds GC (SAVE → SAVEGC). Use a distinct name to avoid collisions.'
                if direction == 'pc_gc' else
                'Blank preserves the profile name when changing regions. For the same edition, enter a different name.'
            ))
        if direction == 'gc_gc':
            self.advanced_checkbox.pack_forget()
        else:
            self.advanced_checkbox.pack(anchor='w')
        self.template_label.configure(text='PC template (extensionless file)' if direction == 'gc_pc'
                                      else 'GameCube template (.gci)')
        self._toggle_template()
        if direction == 'pc_gc':
            self.source_region.set('USA is the only GameCube edition verified in-game.')
        else:
            self.source_region.set('Source GameCube edition: detected when inspecting a save')

    def _browse_source(self):
        if self.direction == 'pc_gc':
            path = filedialog.askopenfilename(title='Select PC save', filetypes=[('All files', '*.*')])
            if path:
                self.pc_in.set(path)
        else:
            path = filedialog.askopenfilename(title='Select GameCube save',
                        filetypes=[('GameCube saves (*.gci)', '*.gci'), ('All files', '*.*')])
            if path:
                self.gc_in.set(path)
                try:
                    game_id = gamecube_game_id(Path(path).read_bytes())
                    self.source_region.set(f'Source GameCube edition: {GAMECUBE_REGIONS[game_id]} ({game_id})')
                    if self.direction == 'gc_gc' and self._selected_game_id() == game_id:
                        target = 'GOWP69' if game_id == 'GOWE69' else 'GOWE69'
                        self.region_choice.set(next(k for k, v in REGION_LABELS.items() if v == target))
                except (OSError, ConversionError):
                    self.source_region.set('Source edition not recognized. Use Inspect save for details.')

    def _browse_output(self):
        path = filedialog.askdirectory(title='Choose output folder')
        if path:
            {'gc_pc': self.pc_out, 'pc_gc': self.gc_out, 'gc_gc': self.gc_gc_out}[self.direction].set(path)

    def _toggle_template(self):
        if self.use_template.get() and self.direction != 'gc_gc':
            self.template_row.pack(fill='x')
        else:
            self.template_row.pack_forget()

    def _browse_template(self):
        types = [('GameCube save (*.gci)', '*.gci'), ('All files', '*.*')] if self.direction == 'pc_gc' else [('All files', '*.*')]
        path = filedialog.askopenfilename(title='Optional destination-platform template', filetypes=types)
        if path:
            self.template_path.set(path)

    def _log(self, msg):
        self.log.configure(state='normal')
        self.log.insert('end', msg + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _inputs(self):
        kind = 'pc' if self.direction == 'pc_gc' else 'gc'
        source_path = self.pc_in.get().strip() if kind == 'pc' else self.gc_in.get().strip()
        if not source_path:
            raise ConversionError('Choose the source save first.')
        source = Path(source_path)
        if not source.is_file():
            raise ConversionError(f'Source save not found: {source}')
        outvar = {'gc_pc': self.pc_out, 'pc_gc': self.gc_out, 'gc_gc': self.gc_gc_out}[self.direction]
        folder = Path(outvar.get().strip()) if outvar.get().strip() else source.parent
        if not folder.is_dir():
            raise ConversionError(f'Output folder does not exist: {folder}')
        template = None
        donor = None
        if self.direction != 'gc_gc' and self.use_template.get():
            if not self.template_path.get().strip():
                raise ConversionError('Choose a template or uncheck Advanced compatibility.')
            donor = Path(self.template_path.get().strip())
            if not donor.is_file():
                raise ConversionError(f'Template save not found: {donor}')
            template = donor.read_bytes()
        return source, source.read_bytes(), donor, template, folder, kind

    def _summary(self, label, data, kind):
        info = describe(data, kind)
        region = f" | {info['game_id']}" if kind == 'gc' else ''
        self._log(f"{label}: {info['name']}{region} | ${info['cash']:,} | Blacklist {info['blacklist']} | career {'started' if info['career_started'] else 'not started'} | {info['race_entries']} race records")
        return info

    def _cash(self):
        if not self.cash_enabled.get():
            return None
        try:
            cash = int(self.cash_value.get().replace(',', '').strip())
        except ValueError as exc:
            raise ConversionError('Cash override must be a whole number.') from exc
        if not 0 <= cash <= 2_000_000_000:
            raise ConversionError('Cash override must be between 0 and 2,000,000,000.')
        return cash

    def inspect(self):
        try:
            _, source, _, template, _, kind = self._inputs()
            info = self._summary('Source', source, kind)
            if kind == 'gc':
                game_id = info['game_id']
                self.source_region.set(f'Source GameCube edition: {GAMECUBE_REGIONS[game_id]} ({game_id})')
            if template is not None:
                self._summary('Custom template', template, 'pc' if kind == 'gc' else 'gc')
            elif self.direction == 'gc_gc':
                self._log('GameCube -> GameCube preserves the original native gameplay block.')
            else:
                self._log('Built-in destination-platform scaffold selected. No donor required.')
            self._log('Save integrity verified. This does not guarantee in-game regional compatibility.')
        except (ConversionError, OSError) as exc:
            self._log('ERROR: ' + str(exc))
            messagebox.showerror('Cannot inspect save', str(exc))
        except Exception as exc:
            self._log('Unexpected error: ' + repr(exc))
            messagebox.showerror('Unexpected error', str(exc))

    @staticmethod
    def _check_gci_name_collision(folder: Path, game_id: str, name: str, target: Path):
        """Dolphin keys saves by 6-character game ID plus internal filename."""
        internal = b'NFSMW' + name.encode('ascii')
        for candidate in folder.iterdir():
            if not candidate.is_file() or candidate.suffix.lower() != '.gci':
                continue
            if candidate.resolve() == target.resolve():
                continue
            try:
                with candidate.open('rb') as handle:
                    header = handle.read(0x40)
            except OSError:
                continue
            if (len(header) >= 0x28 and header[:6] == game_id.encode('ascii')
                    and header[8:0x28].split(b'\x00', 1)[0] == internal):
                raise ConversionError(
                    f'{game_id} / NFSMW{name} already exists in {candidate.name}. '
                    'Choose another internal name; renaming the Windows .gci filename will not fix it.')

    def convert(self):
        try:
            source_path, source, donor_path, template, folder, kind = self._inputs()
            cash = self._cash()
            source_info = self._summary('Source', source, kind)
            if kind == 'gc':
                game_id = source_info['game_id']
                self.source_region.set(f'Source GameCube edition: {GAMECUBE_REGIONS[game_id]} ({game_id})')
            if template is not None:
                self._summary('Custom template', template, 'pc' if kind == 'gc' else 'gc')
            if self.direction == 'gc_pc':
                result = gc_to_pc(source, pc_template=template, cash=cash)
                name = profile_name(result, 'pc')
                target = folder / name / name
                out_kind = 'pc'
            elif self.direction == 'pc_gc':
                game_id = self._selected_game_id()
                result = pc_to_gc(source, gc_template=template, cash=cash,
                                  new_name=self.pc_gc_profile_name.get().strip() or None,
                                  game_id=game_id)
                name = profile_name(result, 'gc')
                target = folder / f'{name}-{game_id}-converted.gci'
                out_kind = 'gc'
            else:
                game_id = self._selected_game_id()
                result = gc_to_gc(source, game_id, new_name=self.gc_gc_profile_name.get().strip() or None, cash=cash)
                name = profile_name(result, 'gc')
                target = folder / f'{name}-{game_id}-converted.gci'
                out_kind = 'gc'
            if target.resolve() == source_path.resolve():
                raise ConversionError('Output path matches the source save. Choose another output folder.')
            if donor_path is not None and target.resolve() == donor_path.resolve():
                raise ConversionError('Output path matches the advanced template. Choose another output folder.')
            if out_kind == 'gc':
                self._check_gci_name_collision(folder, game_id, name, target)
            self._summary('Converted', result, out_kind)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if not messagebox.askyesno('Existing output',
                    f'{target} already exists.\n\nCreate a timestamped backup and replace it?', icon='warning'):
                    self._log('Canceled. Existing output was not changed.')
                    return
                stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
                backup = target.with_name(target.name + '.backup-' + stamp)
                backup.write_bytes(target.read_bytes())
                self._log('Backup created: ' + str(backup))
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.crosssave-', delete=False) as handle:
                    handle.write(result)
                    temp_path = Path(handle.name)
                if temp_path.read_bytes() != result:
                    raise ConversionError('Output write verification failed')
                os.replace(temp_path, target)
            finally:
                if temp_path is not None and temp_path.exists():
                    temp_path.unlink()
            written = target.read_bytes()
            parse_pc(written) if out_kind == 'pc' else parse_gci(written)
            self._last_output = target.parent
            self.open_button.configure(state='normal')
            self._log('SUCCESS: ' + str(target))
            if out_kind == 'gc':
                self._log(f'GameCube identity: {game_id} / NFSMW{name}.')
            if ((kind == 'gc' and source_info['game_id'] != 'GOWE69') or
                (out_kind == 'gc' and game_id != 'GOWE69')):
                self._log('EXPERIMENTAL REGION: Output is structurally valid but requires in-game testing.')
            self._log('File reread and verified; original source remains unchanged.')
            messagebox.showinfo('Conversion completed',
                f'Saved and verified:\n{target}\n\nOriginal save unchanged. Keep backups.\n'
                + ('\nCross-region conversion requires an in-game test.' if self.direction == 'gc_gc' else ''))
        except (ConversionError, OSError) as exc:
            self._log('ERROR: ' + str(exc))
            messagebox.showerror('Conversion failed', str(exc))
        except Exception as exc:
            self._log('Unexpected error: ' + repr(exc))
            self._log(traceback.format_exc())
            messagebox.showerror('Unexpected error', str(exc))

    def open_output(self):
        if self._last_output is not None and self._last_output.is_dir():
            if os.name == 'nt':
                os.startfile(str(self._last_output))
            else:
                self._log('Output folder: ' + str(self._last_output))


if __name__ == '__main__':
    CrossSaveApp().mainloop()
