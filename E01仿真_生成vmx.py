import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import shutil
import sys
import re
import threading
from pathlib import Path

# --- 自动检测工具路径（支持脚本和 exe 两种运行模式） ---
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

BASE_DIR = get_base_dir()
EWFEXPORT_PATH = str(BASE_DIR / "ewf-tools-win64-main" / "ewf-tools" / "ewfexport.exe")
QEMU_IMG_PATH = str(BASE_DIR / "Tools" / "qemu-img.exe")
# --- 配置区结束 ---


class E01ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("E01 到 VMDK 转换器")
        self.root.geometry("600x620")
        self.root.resizable(False, False)

        # 样式
        self.style = ttk.Style()
        self.style.configure("TFrame", padding=10, relief="flat")
        self.style.configure("TLabel", font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"))
        self.style.configure("TEntry", font=("Segoe UI", 10))
        self.style.configure("TCombobox", font=("Segoe UI", 10))
        self.style.configure("TProgressbar", thickness=18)

        # 主框架
        main_frame = ttk.Frame(root, padding="15 15 15 15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # E01文件路径选择
        path_frame = ttk.LabelFrame(main_frame, text="1. E01 文件路径", padding="10")
        path_frame.pack(fill=tk.X, pady=10)

        self.e01_path_entry = ttk.Entry(path_frame, width=60)
        self.e01_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.browse_button = ttk.Button(path_frame, text="浏览...", command=self.browse_e01_file)
        self.browse_button.pack(side=tk.RIGHT)

        # 输出目录选择
        output_frame = ttk.LabelFrame(main_frame, text="2. 输出目录 (VMDK和VMX将生成在此)", padding="10")
        output_frame.pack(fill=tk.X, pady=10)

        self.output_dir_entry = ttk.Entry(output_frame, width=60)
        self.output_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.browse_output_button = ttk.Button(output_frame, text="选择目录...", command=self.browse_output_dir)
        self.browse_output_button.pack(side=tk.RIGHT)

        # 操作系统和启动方式选择
        vm_config_frame = ttk.LabelFrame(main_frame, text="3. 虚拟机配置 (用于生成VMX)", padding="10")
        vm_config_frame.pack(fill=tk.X, pady=10)

        # 操作系统类型
        ttk.Label(vm_config_frame, text="操作系统类型:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.os_type_options = [
            "Windows 10 64-bit", "Windows 8 64-bit", "Windows 7 64-bit",
            "Windows XP 32-bit", "Windows 2003 Server 32-bit",
            "Ubuntu 64-bit", "Debian 64-bit", "CentOS 64-bit", "Other Linux 64-bit",
            "Other 64-bit", "Other 32-bit"
        ]
        self.os_type_var = tk.StringVar(root)
        self.os_type_var.set(self.os_type_options[0])
        self.os_type_menu = ttk.Combobox(vm_config_frame, textvariable=self.os_type_var,
                                         values=self.os_type_options, state="readonly", width=30)
        self.os_type_menu.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        # 启动方式
        ttk.Label(vm_config_frame, text="启动方式:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.boot_type_options = ["BIOS", "EFI (UEFI)"]
        self.boot_type_var = tk.StringVar(root)
        self.boot_type_var.set(self.boot_type_options[0])
        self.boot_type_menu = ttk.Combobox(vm_config_frame, textvariable=self.boot_type_var,
                                           values=self.boot_type_options, state="readonly", width=30)
        self.boot_type_menu.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        # 转换按钮
        self.convert_button = ttk.Button(main_frame, text="开始转换", command=self.start_conversion, style="TButton")
        self.convert_button.pack(pady=15, ipadx=20, ipady=8)

        # --- 进度区域 ---
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=5)

        # 状态文字
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var,
                                      font=("Segoe UI", 9, "bold"), foreground="#333333")
        self.status_label.pack(anchor=tk.W)

        # 进度条
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal",
                                            length=550, mode="determinate", style="TProgressbar")
        self.progress_bar.pack(fill=tk.X, pady=(2, 0))

        # 进度百分比文字
        self.progress_pct_var = tk.StringVar(value="")
        self.progress_pct_label = ttk.Label(progress_frame, textvariable=self.progress_pct_var,
                                            font=("Consolas", 8), foreground="#666666", anchor=tk.E)
        self.progress_pct_label.pack(fill=tk.X)

        # 日志输出
        log_frame = ttk.LabelFrame(main_frame, text="日志输出", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = tk.Text(log_frame, height=7, state="disabled", font=("Consolas", 9), bg="#f0f0f0", wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text_scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        self.log_text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=self.log_text_scrollbar.set)

        self.initial_dir_set = False
        self._cancel_flag = False

    def log_message(self, message):
        """向日志框输出信息"""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def set_status(self, text, progress_pct=None):
        """更新状态文字和进度百分比"""
        self.status_var.set(text)
        if progress_pct is not None:
            self.progress_pct_var.set(f"{progress_pct:.1f}%")
        self.root.update_idletasks()

    def update_progress(self, current_value):
        """更新进度条数值"""
        self.progress_bar["value"] = current_value
        self.root.update_idletasks()

    def browse_e01_file(self):
        """选择E01文件"""
        file_path = filedialog.askopenfilename(
            title="选择 E01 文件",
            filetypes=[("E01 Files", "*.e01"), ("All Files", "*.*")]
        )
        if file_path:
            self.e01_path_entry.delete(0, tk.END)
            self.e01_path_entry.insert(0, file_path)
            if not self.initial_dir_set:
                output_dir = Path(file_path).parent
                self.output_dir_entry.delete(0, tk.END)
                self.output_dir_entry.insert(0, str(output_dir))
                self.initial_dir_set = True

    def browse_output_dir(self):
        """选择输出目录"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir_entry.delete(0, tk.END)
            self.output_dir_entry.insert(0, dir_path)
            self.initial_dir_set = True

    def run_command_live(self, command, description, cwd=None, input_data=None,
                         progress_range=(0, 100), progress_parser=None):
        """
        实时执行外部命令，边执行边读取输出，解析进度信息。

        Args:
            command: 命令列表
            description: 描述文字
            cwd: 工作目录
            input_data: 发送到 stdin 的文本（字符串）
            progress_range: (起始进度, 结束进度)，用于映射到总进度条
            progress_parser: 函数(line) -> 该行解析出的进度百分比(0-100) 或 None
        Returns:
            bool: 是否成功
        """
        self.log_message(f"--- 正在执行: {description} ---")
        self.log_message(f"命令: {' '.join(command)}")
        self.set_status(description)

        base_start, base_end = progress_range
        progress_span = base_end - base_start

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                bufsize=1,
                text=True,
                encoding='utf-8',
                errors='replace',
            )

            # 如果有输入数据，写入 stdin 并关闭
            if input_data:
                process.stdin.write(input_data)
            process.stdin.close()

            stdout_lines = []
            stderr_lines = []
            lock = threading.Lock()

            def read_stream(stream, lines_list):
                for line in iter(stream.readline, ''):
                    with lock:
                        lines_list.append(line)
                        stripped = line.rstrip('\n\r')
                        if stripped:
                            self.log_message(f"  {stripped}")
                        # 尝试解析进度
                        if progress_parser:
                            try:
                                pct = progress_parser(stripped)
                                if pct is not None:
                                    mapped = base_start + progress_span * pct / 100.0
                                    self.update_progress(mapped)
                                    self.set_status(description, progress_pct=mapped)
                            except Exception:
                                pass
                stream.close()

            stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_lines))
            stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_lines))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()

            stdout_thread.join()
            stderr_thread.join()
            process.wait()

            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)

            if process.returncode != 0:
                self.log_message(f"错误: {description} 命令执行失败，返回码 {process.returncode}")
                if stdout.strip():
                    self.log_message("标准输出:\n" + stdout)
                if stderr.strip():
                    self.log_message("标准错误:\n" + stderr)
                    # 尝试 gbk 解码
                    try:
                        stderr_gbk = stderr.encode('utf-8').decode('gbk', errors='replace')
                        if stderr_gbk != stderr:
                            self.log_message("标准错误 (GBK 解码尝试):\n" + stderr_gbk)
                    except Exception:
                        pass
                messagebox.showerror("错误", f"{description} 失败！\n请检查日志获取详情。")
                return False
            else:
                self.log_message("命令执行成功！")
                return True

        except FileNotFoundError:
            self.log_message(f"错误: 找不到 {command[0]}。请检查配置中的工具路径是否正确。")
            messagebox.showerror("错误", f"找不到 {command[0]}。\n请检查配置中的工具路径是否正确。")
            return False
        except Exception as e:
            self.log_message(f"执行 {description} 时发生未知错误: {e}")
            messagebox.showerror("错误", f"未知错误: {e}")
            return False

    def generate_vmx_content(self, vmdk_filename, os_type_selected, boot_type_selected):
        """根据选择生成VMX文件内容"""
        os_type_map = {
            "Windows 10 64-bit": "windows9-64",
            "Windows 8 64-bit": "windows8-64",
            "Windows 7 64-bit": "windows7-64",
            "Windows XP 32-bit": "winxp",
            "Windows 2003 Server 32-bit": "winnetstandard",
            "Ubuntu 64-bit": "ubuntu-64",
            "Debian 64-bit": "debian9-64",
            "CentOS 64-bit": "centos7-64",
            "Other Linux 64-bit": "otherlinux-64",
            "Other 64-bit": "other-64",
            "Other 32-bit": "other"
        }
        vmware_guest_os = os_type_map.get(os_type_selected, "other-64")

        firmware_setting = ""
        if boot_type_selected == "EFI (UEFI)":
            firmware_setting = "firmware = \"efi\""

        vmx_content = f"""
.encoding = "GBK"
config.version = "8"
virtualHW.version = "17"
vmci0.present = "TRUE"
memsize = "4096"
numvcpus = "2"
displayName = "{Path(vmdk_filename).stem}_converted_vm"
guestOS = "{vmware_guest_os}"

{firmware_setting}

ide0:0.fileName = "{vmdk_filename}"
ide0:0.present = "TRUE"
ide0:0.redo = ""

ethernet0.present = "TRUE"
ethernet0.connectionType = "nat"
ethernet0.virtualDev = "e1000"
ethernet0.wakeOnPcktRcv = "FALSE"

usb.present = "TRUE"
usb.autoConnect.enabled = "TRUE"

sound.present = "TRUE"
sound.virtualDev = "hdaudio"

ide1:0.present = "TRUE"
ide1:0.deviceType = "atapi-cdrom"
ide1:0.startConnected = "FALSE"
ide1:0.autodetect = "TRUE"

isolation.tools.hgfs.disable = "TRUE"
mks.enable3d = "TRUE"
bios.bootdelay = "2000"

tools.syncTime = "TRUE"
tools.upgrade.policy = "manual"

snapshot.action = "autoCommit"
snapshot.numSnapshots = "0"

"""
        return vmx_content.strip()

    def parse_ewf_progress(self, line):
        """解析 ewfexport 的进度行，例如: 'Progress: 45%' 或 '45%'"""
        m = re.search(r'Progress\s*:\s*(\d+)', line, re.IGNORECASE)
        if m:
            return float(m.group(1))
        m = re.search(r'(\d+)\s*%', line)
        if m:
            return float(m.group(1))
        return None

    def parse_qemu_progress(self, line):
        """解析 qemu-img -p 的进度行，例如: '(45.00/100.00)' 或 '(45.00/100.00%)'"""
        m = re.search(r'\((\d+\.?\d*)\s*/\s*100\.?\d*\)', line)
        if m:
            return float(m.group(1))
        return None

    def start_conversion(self):
        """开始整个转换流程"""
        e01_path_str = self.e01_path_entry.get().strip()
        output_dir_str = self.output_dir_entry.get().strip()
        os_type_selected = self.os_type_var.get()
        boot_type_selected = self.boot_type_var.get()

        if not e01_path_str:
            messagebox.showwarning("输入错误", "请选择 E01 文件。")
            return
        if not output_dir_str:
            messagebox.showwarning("输入错误", "请选择输出目录。")
            return
        if not Path(EWFEXPORT_PATH).is_file():
            messagebox.showerror("工具错误", f"找不到 ewfexport.exe。请检查配置中的路径: {EWFEXPORT_PATH}")
            return
        if not Path(QEMU_IMG_PATH).is_file():
            messagebox.showerror("工具错误", f"找不到 qemu-img.exe。请检查配置中的路径: {QEMU_IMG_PATH}")
            return

        e01_path = Path(e01_path_str)
        output_dir = Path(output_dir_str)
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = e01_path.stem
        raw_path = output_dir / f"{base_name}.raw"
        vmdk_path = output_dir / f"{base_name}.vmdk"
        vmx_path = output_dir / f"{base_name}.vmx"

        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        self.log_message("--- 开始转换流程 ---")
        self.progress_bar["value"] = 0
        self.progress_pct_var.set("0.0%")
        self.set_status("就绪")
        self.convert_button.config(state="disabled")

        try:
            # ====== 阶段1: E01 → RAW ======
            ewf_input_data = f"\n{raw_path.stem}\n\n\n\n"
            ewf_command = [
                EWFEXPORT_PATH,
                str(e01_path),
                "-f", "raw",
            ]
            if not self.run_command_live(
                ewf_command, "阶段1/3: E01 → RAW 导出中...",
                cwd=output_dir,
                input_data=ewf_input_data,
                progress_range=(0, 40),
                progress_parser=self.parse_ewf_progress,
            ):
                raise Exception("E01 转换失败")
            self.update_progress(40)
            self.set_status("阶段1/3: E01 → RAW 完成", progress_pct=40.0)

            # ====== 阶段2: RAW → VMDK ======
            qemu_command = [
                QEMU_IMG_PATH,
                "convert",
                "-p",                # 启用进度显示
                "-f", "raw",
                "-O", "vmdk",
                str(raw_path),
                str(vmdk_path),
            ]
            if not self.run_command_live(
                qemu_command, "阶段2/3: RAW → VMDK 转换中...",
                cwd=output_dir,
                progress_range=(40, 85),
                progress_parser=self.parse_qemu_progress,
            ):
                raise Exception("RAW 转换失败")
            self.update_progress(85)
            self.set_status("阶段2/3: RAW → VMDK 完成", progress_pct=85.0)

            # ====== 阶段3: 生成 VMX ======
            self.set_status("阶段3/3: 正在生成 VMX 文件...", progress_pct=85.0)
            self.log_message(f"阶段3/3: 正在生成 VMX 文件 ({vmx_path})...")
            vmx_content = self.generate_vmx_content(vmdk_path.name, os_type_selected, boot_type_selected)
            try:
                with open(vmx_path, "w", encoding="utf-8") as f:
                    f.write(vmx_content)
                self.log_message(f"VMX 文件已成功生成: {vmx_path}")
            except Exception as e:
                self.log_message(f"错误: 生成 VMX 文件失败: {e}")
                raise Exception("VMX 生成失败")
            self.update_progress(90)
            self.set_status("VMX 生成完成", progress_pct=90.0)

            # ====== 阶段4: 清理中间 RAW 文件 ======
            self.set_status("正在清理中间文件...", progress_pct=90.0)
            self.log_message(f"正在删除中间产物 RAW 文件 ({raw_path})...")
            try:
                os.remove(raw_path)
                self.log_message("RAW 文件删除成功。")
            except OSError as e:
                self.log_message(f"警告: 删除 RAW 文件失败: {e}")
                messagebox.showwarning("警告", f"删除中间产物 RAW 文件失败。\n请手动删除: {raw_path}")
            self.update_progress(100)
            self.set_status("全部完成 ✓", progress_pct=100.0)

            self.log_message("--- 所有操作完成！ ---")
            messagebox.showinfo("完成", f"E01 文件已成功转换为 VMDK，并生成 VMX 文件！\n\nVMDK: {vmdk_path}\nVMX: {vmx_path}")

        except Exception as e:
            self.log_message(f"流程中断: {e}")
            self.log_message("--- 转换流程失败 ---")
            self.set_status("转换失败", progress_pct=0)
        finally:
            self.convert_button.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = E01ConverterApp(root)
    root.mainloop()
