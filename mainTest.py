import os
import threading
import queue
import traceback
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.scrolledtext as scrolledtext
from tkinter import messagebox
from tkinter.filedialog import askopenfilename
from ttkwidgets import CheckboxTreeview
import yaml

# Domain workers (unchanged imports)
from Swagger2Csv import swag_wsid as swag
from Swagger2Csv import wsid_swag as wsid
from Swagger2Csv import create_error_yaml as wsidToErr
from Swagger2Csv import wsid_possible_values_yaml as wsidToPosibleValues
from Swagger2Csv import create_possible_values_tab as createPVL

# Centralized UI option matrix
OPTIONS = {
    "1": {"yaml_btn": True,  "xls_btn": False, "show_inline": False, "show_tree": True,  "reset_paths": ["xlsx"]},
    "2": {"yaml_btn": True,  "xls_btn": True,  "show_inline": True,  "show_tree": False, "reset_paths": []},
    "3": {"yaml_btn": False, "xls_btn": True,  "show_inline": False, "show_tree": False, "reset_paths": ["yaml","xlsx"]},
    "4": {"yaml_btn": False, "xls_btn": True,  "show_inline": False, "show_tree": False, "reset_paths": ["yaml"]},
    "5": {"yaml_btn": False, "xls_btn": True,  "show_inline": False, "show_tree": False, "reset_paths": ["yaml"]},
}

class App:
    def __init__(self) -> None:
        # Root first — always
        self.root = tk.Tk()
        self.root.title("Swagger2WSID")
        self.root.configure(background="black")
        self.root.geometry("500x720")  # a bit wider for paths
        self.root.eval('tk::PlaceWindow . center')

        # State
        self.choice = tk.StringVar(master=self.root, value="1")
        self.yaml_path = ""
        self.xlsx_path = ""
        self.is_enable_inline = True
        self.checkbox_resource_mapping = {}
        self.result_queue: queue.Queue = queue.Queue()

        # Build UI
        self._build_styles()
        self._build_header()
        self._build_inputs()
        self._build_tree()
        self._build_actions()
        self._build_output()

        # Apply default option state
        self._apply_option("1")

    # ---------- Styles ----------
    def _build_styles(self) -> None:
        s = ttk.Style(master=self.root)
        s.configure('unchecked.TRadiobutton', background='black', foreground='white', font=('Arial', 12, 'bold'))
        s.configure('checked.TRadiobutton',   background='green', foreground='white', font=('Arial', 12, 'bold'))
        s.configure("Checkbox.Treeview", background="black",
                    fieldbackground="black", foreground="white", font=('Arial', 9, 'bold'), rowheight=22)

    # ---------- Top choices (R1..R5) ----------
    def _build_header(self) -> None:
        frm = ttk.Frame(self.root, padding=(8,8,8,8))
        frm.configure(style='unchecked.TRadiobutton')  # background only
        frm.grid(row=0, column=0, sticky="w")

        def rb(text, val, r):
            b = ttk.Radiobutton(
                frm, text=text, value=val, variable=self.choice,
                command=lambda v=val: self._on_choice(v), style='unchecked.TRadiobutton'
            )
            b.grid(row=r, column=0, sticky="w", pady=3)
            return b

        self.rb_map = {
            "1": rb("SWAGGER to WSID",                  "1", 0),
            "2": rb("WSID to SWAGGER",                  "2", 1),
            "3": rb("WSID to ERROR CODE YAML",          "3", 2),
            "4": rb("WSID to Possible Values YAML",     "4", 3),
            "5": rb("Update PVL from Resource Details", "5", 4),
        }

    # ---------- File pickers + inline toggle ----------
    def _build_inputs(self) -> None:
        self.inputs = ttk.Frame(self.root)
        self.inputs.grid(row=1, column=0, sticky="we", padx=8)
        self.inputs.columnconfigure(1, weight=1)

        self.yml_label = ttk.Label(self.inputs, text="Choose Input Yaml File :", background='black', foreground='white', font=('Arial', 12, 'bold'))
        self.yml_label.grid(row=0, column=0, sticky="w", pady=4)
        self.yml_btn = tk.Button(self.inputs, text='Disabled', state=tk.DISABLED, command=self._open_yaml_file, bg='#424040', fg='white',
                                 font='Arial 9 bold', height=1, width=10)
        self.yml_btn.grid(row=0, column=1, sticky="w", pady=4)

        self.xls_label = ttk.Label(self.inputs, text="Choose Input Xlsx File:", background='black', foreground='white', font=('Arial', 12, 'bold'))
        self.xls_label.grid(row=1, column=0, sticky="w", pady=4)
        self.xls_btn = tk.Button(self.inputs, text='Disabled', state=tk.DISABLED, command=self._open_excel_file, bg='#424040', fg='white',
                                 font='Arial 9 bold', height=1, width=10)
        self.xls_btn.grid(row=1, column=1, sticky="w", pady=4)

        self.enable_inline_btn = tk.Button(self.inputs, text="Inline Defs Enabled", width=20, command=self._toggle_inline_button,
                                           relief="raised", bg='#2a4f2b', fg='white', font='Arial 11 bold')
        # Visibility toggled by options

    # ---------- Resource tree ----------
    def _build_tree(self) -> None:
        self.tree_frame = ttk.Frame(self.root)
        self.tree_frame.grid(row=2, column=0, sticky="news", padx=8, pady=(6, 0))
        self.root.rowconfigure(2, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.v_tree_scroll = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL)
        self.x_tree_scroll = ttk.Scrollbar(self.tree_frame, orient=tk.HORIZONTAL)
        self.tree = CheckboxTreeview(self.tree_frame, show='tree', height=8,
                                     yscrollcommand=self.v_tree_scroll.set,
                                     xscrollcommand=self.x_tree_scroll.set,
                                     style="Checkbox.Treeview")

        self.v_tree_scroll.config(command=self.tree.yview)
        self.x_tree_scroll.config(command=self.tree.xview)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.v_tree_scroll.grid(row=0, column=1, sticky="ns")
        self.x_tree_scroll.grid(row=1, column=0, sticky="ew")
        self.tree_frame.rowconfigure(0, weight=1)
        self.tree_frame.columnconfigure(0, weight=1)

    # ---------- Start / Progress ----------
    def _build_actions(self) -> None:
        self.actions = ttk.Frame(self.root)
        self.actions.grid(row=3, column=0, sticky="w", padx=8, pady=6)

        self.start_btn = tk.Button(self.actions, text='Start', command=self._start_process, bg='#083740', fg='white',
                                   font='Arial 11 bold', height=2, width=10)
        self.start_btn.grid(row=0, column=0, sticky="w")

        self.pb = ttk.Progressbar(self.actions, orient='horizontal', mode='indeterminate', length=280)
        self.pb.grid(row=0, column=1, sticky="w", padx=10)
        self.pb.grid_remove()

    # ---------- Output ----------
    def _build_output(self) -> None:
        self.out_text = scrolledtext.ScrolledText(self.root, width=62, height=16, wrap='word', background='black', foreground='white')
        self.out_text['font'] = ('Arial', 12, 'bold')
        self.out_text.grid(row=4, column=0, sticky="nsew", padx=8, pady=(2,8))
        self.root.rowconfigure(4, weight=1)

    # ---------- Choice + option handling ----------
    def _on_choice(self, value: str) -> None:
        self._apply_option(value)

    def _apply_option(self, choice: str) -> None:
        cfg = OPTIONS[choice]

        # Reset paths if required
        if "yaml" in cfg["reset_paths"]:
            self.yaml_path = ""
        if "xlsx" in cfg["reset_paths"]:
            self.xlsx_path = ""

        # Enable/disable file buttons
        self._set_yaml_btn(cfg["yaml_btn"])
        self._set_xls_btn(cfg["xls_btn"])

        # Toggle inline button
        if cfg["show_inline"]:
            self.enable_inline_btn.grid(row=2, column=0, sticky="w", pady=6)
        else:
            self.enable_inline_btn.grid_remove()

        # Toggle tree visibility
        if cfg["show_tree"]:
            self.tree_frame.grid()
        else:
            self.tree_frame.grid_remove()

        # Update labels text
        self.yml_label.config(text="Choose Input Yaml File :")
        self.xls_label.config(text="Choose Input Xlsx File:")

        # Update radio styles
        for key, rb in self.rb_map.items():
            rb.configure(style='checked.TRadiobutton' if key == choice else 'unchecked.TRadiobutton')

    def _set_yaml_btn(self, enabled: bool) -> None:
        if enabled:
            self.yml_btn.config(state=tk.NORMAL, text="Browse", bg="#2a4f2b")
            self.yml_label.config(foreground='white', background='black')
        else:
            self.yml_btn.config(state=tk.DISABLED, text="Disabled", bg="#424040")

    def _set_xls_btn(self, enabled: bool) -> None:
        if enabled:
            self.xls_btn.config(state=tk.NORMAL, text="Browse", bg="#2a4f2b")
        else:
            self.xls_btn.config(state=tk.DISABLED, text="Disabled", bg="#424040")

    # ---------- File handlers ----------
    def _open_yaml_file(self) -> None:
        path = askopenfilename(filetypes=[("Yaml files", ".yaml .yml")])
        if not path:
            return
        if not (path.endswith(".yaml") or path.endswith(".yml")):
            messagebox.showwarning("Invalid file", "Please choose a .yaml/.yml file.")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as e:
            messagebox.showerror("YAML error", f"Error reading YAML: {e}")
            return

        self.yaml_path = path
        self.yml_label.config(text=self.yaml_path, foreground='grey')
        self._clear_output()
        self._populate_tree_from_yaml()

    def _open_excel_file(self) -> None:
        path = askopenfilename(filetypes=[("Excel files", ".xlsx .xls")])
        if not path:
            return
        if not (path.endswith(".xlsx") or path.endswith(".xls")):
            messagebox.showwarning("Invalid file", "Please choose an .xlsx/.xls file.")
            return
        self.xlsx_path = path
        self.xls_label.config(text=self.xlsx_path, foreground='grey')
        self._clear_output()

    # ---------- Tree population ----------
    def _populate_tree_from_yaml(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.checkbox_resource_mapping.clear()

        try:
            resource_dict = swag.get_resources(self.yaml_path)
        except Exception as e:
            messagebox.showerror("Parse error", f"Failed to read resources: {e}")
            return

        i = 1
        for resource, operations in resource_dict.items():
            node_id = str(i)
            self.tree.change_state(self.tree.insert("", "end", node_id, text=resource), "checked")
            op_map = {}
            j = i * 10
            for op in operations:
                child_id = str(j)
                self.tree.change_state(self.tree.insert(node_id, "end", child_id, text=op), "checked")
                op_map[child_id] = op
                j += 1
            self.checkbox_resource_mapping[resource] = op_map
            i += 1

        if i > 1:
            self.tree.column("#0", width=340, stretch=True, minwidth=300)
            self.tree.expand_all()

    # ---------- Validation ----------
    def _validate(self) -> bool:
        choice = self.choice.get()
        if choice == "1" and not self.yaml_path:
            messagebox.showinfo("Message", "Please select input YAML file.")
            return False
        if choice == "2" and (not self.xlsx_path or not self.yaml_path):
            messagebox.showinfo("Message", "Please select input XLSX and YAML files.")
            return False
        if choice in ("3","4") and not self.xlsx_path:
            messagebox.showinfo("Message", "Please select input XLSX file.")
            return False
        return True

    # ---------- Start / Stop ----------
    def _start_process(self) -> None:
        if not self._validate():
            return

        choice = self.choice.get()
        self._clear_output()
        self._halt_ui()

        try:
            if choice == "1":
                selected_resources = {}
                for res, id_map in self.checkbox_resource_mapping.items():
                    ops = []
                    for child_id, op_name in id_map.items():
                        if child_id in self.tree.get_checked():
                            ops.append(op_name)
                    selected_resources[res] = ops

                t = threading.Thread(target=self._run_and_queue,
                                     args=(swag.start, (self.yaml_path, selected_resources)))
            elif choice == "2":
                t = threading.Thread(target=self._run_and_queue,
                                     args=(wsid.start, (self.yaml_path, self.xlsx_path, self.is_enable_inline)))
            elif choice == "3":
                t = threading.Thread(target=self._run_and_queue,
                                     args=(wsidToErr.start, (self.xlsx_path,)))
            elif choice == "4":
                t = threading.Thread(target=self._run_and_queue,
                                     args=(wsidToPosibleValues.start, (self.xlsx_path,)))
            else:  # "5"
                # PVL generation runs inline (fast enough + user selects file here)
                xlsx_path = self.xlsx_path or askopenfilename(title="Select WSID Excel File",
                                                              filetypes=[("Excel files", "*.xlsx *.xls")])
                if not xlsx_path:
                    self._resume_ui()
                    return
                createPVL.generate_possible_values_list(xlsx_path)
                self._append_success("\nPossible Values List tab successfully updated from Resource Details!\n")
                self._resume_ui()
                return

            # Threaded cases
            self.pb.grid()
            self.pb.start(10)
            t.daemon = True
            t.start()
            self.root.after(100, self._process_queue)

        except Exception as e:
            self._append_error(f"Error occurred: {e}")
            traceback.print_exc()
            self._resume_ui()

    def _run_and_queue(self, fn, args):
        try:
            result = fn(*args)
        except Exception as e:
            # Normalize result to match your prior structure
            result = type('', (object,), {"result_string": f'Error Occurred: {e}', "warning_msg": '', "is_error": True})()
        self.result_queue.put(result)

    def _process_queue(self):
        try:
            result = self.result_queue.get_nowait()
        except queue.Empty:
            self.root.after(150, self._process_queue)
            return

        color_tag = 'ok' if not getattr(result, "is_error", False) else 'err'
        self.out_text.tag_config('ok',  foreground='green')
        self.out_text.tag_config('warn', foreground='#facd50')
        self.out_text.tag_config('err', foreground='red')

        self._clear_output()
        self.out_text.insert(tk.INSERT, getattr(result, "result_string", "") + '\n', color_tag)
        self.out_text.insert(tk.INSERT, getattr(result, "warning_msg", ""), 'warn')

        self.pb.stop()
        self.pb.grid_remove()
        self._resume_ui()

    # ---------- UI helpers ----------
    def _toggle_inline_button(self) -> None:
        # “Enabled” state is green/raised; clicking toggles to disabled (sunken/gray)
        if self.is_enable_inline:
            self.enable_inline_btn.config(relief="sunken", text="Inline Defs Disabled", bg="#424040")
            self.is_enable_inline = False
        else:
            self.enable_inline_btn.config(relief="raised", text="Inline Defs Enabled", bg="#2a4f2b")
            self.is_enable_inline = True

    def _halt_ui(self) -> None:
        self.yml_btn.config(state=tk.DISABLED, text="Disabled", bg="#424040")
        self.xls_btn.config(state=tk.DISABLED, text="Disabled", bg="#424040")
        self.enable_inline_btn.config(state=tk.DISABLED)
        for rb in self.rb_map.values():
            rb.config(state=tk.DISABLED)
        self.start_btn.config(state=tk.DISABLED)

    def _resume_ui(self) -> None:
        cfg = OPTIONS[self.choice.get()]
        self._set_yaml_btn(cfg["yaml_btn"])
        self._set_xls_btn(cfg["xls_btn"])
        self.enable_inline_btn.config(state=tk.NORMAL)
        for rb in self.rb_map.values():
            rb.config(state=tk.NORMAL)
        self.start_btn.config(state=tk.NORMAL)

    def _append_success(self, msg: str) -> None:
        self.out_text.insert(tk.INSERT, msg)
        self.out_text.tag_config('ok', foreground='green')

    def _append_error(self, msg: str) -> None:
        self.out_text.insert(tk.INSERT, msg)
        self.out_text.tag_config('err', foreground='red')

    def _clear_output(self) -> None:
        self.out_text.delete(1.0, tk.END)

    # ---------- Main loop ----------
    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
