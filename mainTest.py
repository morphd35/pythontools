
import os
import yaml
import traceback
import concurrent
import threading
from tkinter import *
import tkinter as tk
from ttkwidgets import CheckboxTreeview
from tkinter.ttk import *
import tkinter.ttk as ttk

# importing askopenfile function
# from class filedialog
from tkinter.filedialog import askopenfilename
from tkinter import messagebox
import tkinter.scrolledtext as scrolledtext
import traceback
import queue

from Swagger2Csv import swag_wsid as swag
from Swagger2Csv import wsid_swag as wsid
# from Swagger2Csv import wsid_err_yaml as wsidToErr
from Swagger2Csv import create_error_yaml as wsidToErr
from Swagger2Csv import wsid_possible_values_yaml as wsidToPosibleValues
from Swagger2Csv import create_possible_values_tab as createPVL


# ----------------------------
# MODULE-LEVEL CONFIGURATION
# ----------------------------
# -------------------------------------------------------------------
# OPTIONS CONFIGURATION DICTIONARY
# -------------------------------------------------------------------
# This dictionary defines the behavior of each selectable option
# in the UI (radio buttons R1-R5 currently).
#
# Key: string representing the radio button value ('1', '2', etc.)
# Value: dictionary containing UI and logic settings for that option
#
# Fields inside each option dictionary:
#   - 'yaml_btn': 'enable' or 'disable'
#       Controls whether the YAML file selection button is active.
#   - 'xls_btn': 'enable' or 'disable'
#       Controls whether the XLS/XLSX file selection button is active.
#   - 'checked_radio': string ('R1', 'R2', etc.)
#       Indicates which radio button should appear checked when this
#       option is selected.
#   - 'show_inline': True/False
#       Determines whether the "enable inline" button is displayed.
#   - 'show_tree': True/False
#       Determines whether the resource tree (tree view) is displayed.
#   - 'reset_paths': list of strings, e.g., ['yaml_path', 'xlsx_path']
#       Lists which file path variables should be reset/cleared when
#       this option is selected.
#
# Usage/Modification Notes:
#   - To add a new option:
#       1. Add a new key-value pair here, following the same structure.
#       2. Ensure a corresponding radio button variable exists (e.g., R6).
#       3. Update switch() to handle the new radio button style changes.
#       4. Update start_process() if the new option requires specific
#          processing logic.
#   - This setup centralizes UI behavior control in one dictionary,
#     making it easier to maintain, read, and grow as new features
#     or options are added.
# -------------------------------------------------------------------


options = {
    '1': {
        'yaml_btn': 'enable',
        'xls_btn': 'disable',
        'checked_radio': 'R1',
        'show_inline': False,
        'show_tree': True,
        'reset_paths': ['xlsx_path']
    },
    '2': {
        'yaml_btn': 'enable',
        'xls_btn': 'enable',
        'checked_radio': 'R2',
        'show_inline': True,
        'show_tree': False,
        'reset_paths': []
    },
    '3': {
        'yaml_btn': 'disable',
        'xls_btn': 'enable',
        'checked_radio': 'R3',
        'show_inline': False,
        'show_tree': False,
        'reset_paths': ['xlsx_path', 'yaml_path']
    },
    '4': {
        'yaml_btn': 'disable',
        'xls_btn': 'enable',
        'checked_radio': 'R4',
        'show_inline': False,
        'show_tree': False,
        'reset_paths': ['yaml_path']
    },
    '5': {
        'yaml_btn': 'disable',
        'xls_btn': 'enable',
        'checked_radio': 'R5',
        'show_inline': False,
        'show_tree': False,
        'reset_paths': ['yaml_path']
    }
}

# Global paths
yaml_path = ''
xlsx_path = ''
choice = ''

# -------------------------------------------------------------------
# DYNAMIC RADIO BUTTON CREATION
# -------------------------------------------------------------------
radio_buttons = {}
var = StringVar()
var.set(next(iter(options.keys())))  # default selection

for i, key in enumerate(options.keys(), start=1):
    rb = ttk.Radiobutton(
        root,
        text=f"Option {key}",
        variable=var,
        value=key,
        command=lambda k=key: switch(k)  # pass key to switch
    )
    rb.grid(row=i, column=0, sticky="W", pady=1)
    radio_buttons[key] = rb

class WsidCreationThreadedTask(threading.Thread):
    def __init__(self, queue, yaml_path, selected_resources):
        super().__init__()
        self.yaml_path = yaml_path
        self.selected_resources = selected_resources
        self.queue = queue

    def run(self):
        global result
        try:
            result = swag.start(self.yaml_path, self.selected_resources)
            self.queue.put(result)
        except Exception as e:
            print(str(e))
            result = type('', (object,),
                          {"result_string": 'Error Occurred:  ' + str(e), "warning_msg": '', "is_error": True})()
            self.queue.put(result)


class WsidExtractionThreadedTask(threading.Thread):
    def __init__(self, queue, yaml_path, xlsx_path, is_enable_inline):
        super().__init__()
        self.yaml_path = yaml_path
        self.xlsx_path = xlsx_path
        self.is_enable_inline = is_enable_inline
        self.queue = queue

    def run(self):
        global result
        try:
            result = wsid.start(self.yaml_path, self.xlsx_path, self.is_enable_inline)
            self.queue.put(result)
        except Exception as e:
            print(str(e))
            result = type('', (object,),
                          {"result_string": 'Error Occurred:  ' + str(e), "warning_msg": '', "is_error": True})()
            self.queue.put(result)


class WsidErrorCodeExtractionThreadedTask(threading.Thread):
    def __init__(self, queue, xlsx_path):
        super().__init__()
        self.xlsx_path = xlsx_path
        self.queue = queue

    def run(self):
        global result
        try:
            result = wsidToErr.start(self.xlsx_path)
            self.queue.put(result)
        except Exception as e:
            print(str(e))
            result = type('', (object,),
                          {"result_string": 'Error Occurred:  ' + str(e), "warning_msg": '', "is_error": True})()
            self.queue.put(result)

class WsidPossibleValuesExtractionThreadedTask(threading.Thread):
    def __init__(self, queue, xlsx_path):
        super().__init__()
        self.xlsx_path = xlsx_path
        self.queue = queue

    def run(self):
        global result
        try:
            result = wsidToPosibleValues.start(self.xlsx_path)
            self.queue.put(result)
        except Exception as e:
            print(str(e))
            result = type('', (object,),
                          {"result_string": 'Error Occurred:  ' + str(e), "warning_msg": '', "is_error": True})()
            self.queue.put(result)


root = Tk()
root.geometry('400x600')
# This function will be used to open
# file in read mode and only Python files
# will be opened
choice = ''
checkbox_resource_mapping = {}
is_enable_inline = True
notice = '\nThis can take some time...\n Please be patient'

result = None
result_queue = queue.Queue()


def process_queue():
    try:
        global result
        result = result_queue.get_nowait()
        add_out_text()
    # Show result of the task if needed
    except queue.Empty:
        root.after(2000, process_queue)


def add_out_text():
    color = 'green'
    global result
    if result.is_error:
        color = 'red'
    clear_contents()
    out_text.insert(INSERT, result.result_string + '\n', 'result')
    out_text.insert(INSERT, result.warning_msg, 'warning')
    out_text.tag_config('result', foreground=color)
    out_text.tag_config('warning', foreground='#facd50')
    pb.stop()
    pb.grid_remove()
    resume_ui()
    root.update()


def halt_ui():
    if choice == '2':
        xls_btn["state"] = DISABLED
        xls_btn["text"] = "Disabled"
    yml_btn["state"] = DISABLED
    yml_btn["text"] = "Disabled"
    R1["state"] = DISABLED
    R2["state"] = DISABLED
    R3["state"] = DISABLED
    R4["state"] = DISABLED
    start_btn["state"] = DISABLED
    enable_inline_btn["state"] = DISABLED


def resume_ui():
    if choice == '1':
        change_state_yaml_btn_and_label('enable')
    if choice == '2':
        change_state_yaml_btn_and_label('enable')
        change_state_xls_btn_and_label('enable')
    if choice == '3' or choice =='4':
        change_state_xls_btn_and_label('enable')
    R1["state"] = NORMAL
    R2["state"] = NORMAL
    R3["state"] = NORMAL
    R4["state"] = NORMAL
    enable_inline_btn["state"] = NORMAL
    start_btn["state"] = NORMAL


def toggle_inline_button():
    global is_enable_inline
    if enable_inline_btn.config('relief')[-1] == 'sunken':
        enable_inline_btn.config(relief="raised")
        enable_inline_btn.config(text="Inline Defs Enabled", bg="#2a4f2b")
        is_enable_inline = True

    else:
        enable_inline_btn.config(relief="sunken")
        enable_inline_btn.config(text="Inline Defs Disabled", bg="#424040")
        is_enable_inline = False

def change_state_yaml_btn_and_label(state):
    if state == 'enable':
        yml_btn["state"] = NORMAL
        yml_btn["text"] = "Browse"
        yml_btn["bg"] = '#2a4f2b'
        yml_label["foreground"] = 'white'
        yml_label["background"] = 'black'
    else:
        yml_btn["state"] = DISABLED
        yml_btn["text"] = "Disabled"
        yml_btn['bg'] = '#424040'

def change_state_xls_btn_and_label(state):
    if state == 'enable':
        xls_btn["state"] = NORMAL
        xls_btn["text"] = "Browse"
        xls_btn["bg"] = '#2a4f2b'
    else:
        xls_btn["state"] = DISABLED
        xls_btn["text"] = "Disabled"
        xls_btn['bg'] = '#424040'

# -------------------------------------------------------------------
# SWITCH FUNCTION
# -------------------------------------------------------------------
def switch(selected_key):
    global yaml_path, xlsx_path

    choice = selected_key
    opt = options[choice]

    # Enable/disable buttons
    change_state_yaml_btn_and_label(opt['yaml_btn'])
    change_state_xls_btn_and_label(opt['xls_btn'])

    # Reset paths if required
    for path_var in opt.get('reset_paths', []):
        if path_var == 'yaml_path':
            yaml_path = ''
        elif path_var == 'xlsx_path':
            xlsx_path = ''

    # Show/hide inline and tree
    if opt['show_inline']:
        enable_inline_btn.grid(row=2, column=0, sticky="W", pady=1)
    else:
        enable_inline_btn.grid_remove()

    if opt['show_tree']:
        tree.grid()
        v_tree_scroll.grid()
        x_tree_scroll.grid()
    else:
        tree.grid_remove()
        v_tree_scroll.grid_remove()
        x_tree_scroll.grid_remove()

    # Update radio styles dynamically
    for k, rb in radio_buttons.items():
        rb["style"] = "checked.TRadiobutton" if k == choice else "unchecked.TRadiobutton"

    # Reset labels
    xls_label["text"] = 'Choose Input Xlsx File:'
    yml_label["text"] = 'Choose Input Yaml File:'

def open_yaml_file():
    path = askopenfilename(filetypes=[("Yaml files", ".yaml .yml")])
    global yaml_path
    if path is not None:
        if path.endswith('.yaml') or path.endswith('.yml'):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
            except Exception as e:
                    print(f"Error reading Yaml File: {e}")


            yaml_path = path
            yml_label["text"] = yaml_path
            yml_label["foreground"] = 'grey'
            clear_contents()

            resource_dict = swag.get_resources(yaml_path)
            tree.delete(*tree.get_children())
            i = 1
            for resource in resource_dict.keys():
                tree.change_state(tree.insert("", "end", str(i), text=resource), "checked")
                j = i * 10
                # mapping_list = []
                oper_dict = {}
                for operation in resource_dict[resource]:
                    tree.change_state(tree.insert(str(i), "end", str(j), text=operation), "checked")
                    oper_dict[str(j)] = operation
                    j += 1
                checkbox_resource_mapping[resource] = oper_dict
                i += 1
            if i != 11:
                tree.grid(row=2, column=0, sticky="nswe", pady=1)
                tree.grid_remove()
                tree.column("#0", width=200, stretch=True, minwidth=300)
                if choice == '1':
                    tree.grid(row=2, column=0, sticky="nswe", pady=1)
                    tree.expand_all()
                    v_tree_scroll.grid(row=2, column=1, sticky="ns")
                    x_tree_scroll.grid(row=3, column=0, sticky="news")
            root.update()


def open_excel_file():
    path = askopenfilename(filetypes=[("Excel files", ".xlsx .xls")])
    global xlsx_path
    if path is not None:
        if path.endswith('.xlsx') or path.endswith('.xls'):
            xlsx_path = path
            xls_label["text"] = xlsx_path
            xls_label["foreground"] = 'grey'
            clear_contents()


def validate_input():
    if not choice:
        messagebox.showinfo("Message", "Please select an Option ")
        return False
    if choice == '1':
        if not yaml_path:
            messagebox.showinfo("Message", "Please select input yaml file")
            return False
    elif choice == '2':
        if not xlsx_path or not yaml_path:
            messagebox.showinfo("Message", "Please select input xlsx/yaml file")
            return False
    elif choice == '3' or choice =='4':
        if not xlsx_path:
            messagebox.showinfo("Message", "Please select input xlsx file")
            return False
    return True


def clear_contents():
    out_text.delete(1.0, END)


def start_process():
    if not validate_input():
        return

    opt = options[choice]  # get UI option config

    try:
        clear_contents()
        out_text["foreground"] = 'white'
        pb.grid(row=5, column=0, sticky=W, pady=2)
        pb.start()
        halt_ui()
        root.update()

        if choice == '1':
            # WSID creation task
            selected_resources = {}
            if tree:
                for checked_mapping in checkbox_resource_mapping.keys():
                    oper_list = []
                    selected_resources[checked_mapping] = oper_list
                    for operation in checkbox_resource_mapping[checked_mapping].keys():
                        if operation in tree.get_checked():
                            oper_list.append(checkbox_resource_mapping[checked_mapping][operation])
            t = WsidCreationThreadedTask(result_queue, yaml_path, selected_resources)
        
        elif choice == '2':
            # Business context extraction
            t = WsidExtractionThreadedTask(result_queue, yaml_path, xlsx_path, is_enable_inline)
        
        elif choice in ['3', '4']:
            # Error codes or PV extraction
            if choice == '3':
                t = WsidErrorCodeExtractionThreadedTask(result_queue, xlsx_path)
            else:
                t = WsidPossibleValuesExtractionThreadedTask(result_queue, xlsx_path)

        elif choice == '5':
            # Create/update PVL
            xlsx_path = askopenfilename(
                title="Select WSID Excel File",
                filetypes=[("Excel files", "*.xlsx *.xls")]
            )
            if not xlsx_path:
                messagebox.showwarning("No file selected", "Please select a WSID Excel file to continue.")
                return
            createPVL.generate_possible_values_list(xlsx_path)
            out_text.insert(INSERT, "\nPossible Values List tab successfully updated from Resource Details!\n")
            out_text["foreground"] = 'green'
            return  # no need to start a thread

        # Start the thread if applicable
        if choice != '5':
            t.start()
            root.after(100, process_queue)

    except Exception as e:
        clear_contents()
        out_text.insert(INSERT, f"Error occurred: {str(e)}")
        out_text["foreground"] = 'red'
        traceback.print_exc()
    finally:
        pb.stop()
        pb.grid_remove()
        resume_ui()
        root.update()

s = ttk.Style()
s.configure('unchecked.TRadiobutton', background='black', foreground='white', font='aerial 12 bold')
s.configure('checked.TRadiobutton', background='green', foreground='white', font='aerial 12 bold')
s.configure("Checkbox.Treeview", background="black",
            fieldbackground="black", foreground="white", font='aerial 9 bold', width=300)

var = IntVar()
R1 = Radiobutton(root, text="SWAGGER to WSID", variable=var, value=1, style='unchecked.TRadiobutton', command=switch)
R2 = Radiobutton(root, text="WSID to SWAGGER", variable=var, value=2, style='unchecked.TRadiobutton', command=switch)
R3 = Radiobutton(root, text="WSID to ERROR CODE YAML", variable=var, value=3, style='unchecked.TRadiobutton',command=switch)
R4 = Radiobutton(root, text="WSID to Possible Values YAML", variable=var, value=4, style='unchecked.TRadiobutton',command=switch)
R5 = Radiobutton(root, text="Update PVL from Resource Details", variable=var, value=5, style='unchecked.TRadiobutton', command=switch)

R1.grid(row=0, column=0, sticky=W, pady=3)
R2.grid(row=1, column=0, sticky=W, pady=3)
R3.grid(row=2, column=0, sticky=W, pady=3)
R4.grid(row=3, column=0, sticky=W, pady=3)
R5.grid(row=4, column=0, sticky=W, pady=3)

f1 = tk.Frame(root, background='black')
yml_label = Label(f1, text="Choose Input Yaml File :", wraplength=300, background='black', foreground='white',
                  font='aerial 12 bold')
xls_label = Label(f1, text="Choose Input Xlsx File:", wraplength=300, background='black', foreground='white',
                  font='aerial 12 bold')
yml_label.grid(row=0, column=0, sticky=W, pady=2)
xls_label.grid(row=1, column=0, sticky=W, pady=2)
yml_btn = tk.Button(f1, text='Disabled', state=DISABLED, command=lambda: open_yaml_file(), bg='#424040', fg='white',
                    font='arial 9 bold', height=1, width=8)
xls_btn = tk.Button(f1, text='Disabled', state=DISABLED, command=lambda: open_excel_file(), bg='#424040', fg='white',
                    font='arial 9 bold', height=1, width=8)
yml_btn.grid(row=0, column=1, sticky=W, pady=2)
xls_btn.grid(row=1, column=1, sticky=W, pady=2)
v_tree_scroll = ttk.Scrollbar(f1, orient=tk.VERTICAL)
x_tree_scroll = ttk.Scrollbar(f1, orient=tk.HORIZONTAL)
enable_inline_btn = tk.Button(f1, text="Inline Defs Enabled", width=20, command=lambda: toggle_inline_button(),
                              relief="raised", bg='#2a4f2b', fg='white', font='arial 11 bold')
tree = CheckboxTreeview(f1, show='tree', height=5, yscrollcommand=v_tree_scroll.set, xscrollcommand=x_tree_scroll.set)
v_tree_scroll.config(command=tree.yview)
x_tree_scroll.config(command=tree.xview)
f1.grid(row=5, column=0, sticky=W, pady=2)
start_btn = tk.Button(root, text='Start', command=lambda: start_process(), bg='#083740', fg='white',
                      font='arial 11 bold', height=2, width=8)
start_btn.grid(row=6, column=0, sticky=W, pady=2)
l3 = Label(root, text="", wraplength=300, background='black', foreground='white', font='aerial 12 bold')
l3.grid(row=7, column=0, sticky=W, pady=2)
width, height = 42, 20
pb = ttk.Progressbar(
    root,
    orient='horizontal',
    mode='indeterminate',
    length=400
)
pb.grid(row=8, column=0, sticky=W, pady=2)
out_text = scrolledtext.ScrolledText(width=width, height=height, wrap='word', background='black', foreground='white')
out_text['font'] = ('arial', '12', 'bold')
out_text.grid(row=9, column=0, sticky=W, pady=2)
root.configure(background='black')
root.eval('tk::PlaceWindow . center')
root.title('Swagger2WSID')
mainloop()

