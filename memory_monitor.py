#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, Pango
import subprocess
import threading
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class MemoryCpuMonitorWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Memory & CPU Monitor")
        self.set_border_width(10)
        self.set_default_size(500, 450)

        # Default settings
        self.memory_alert_threshold = 90
        self.cpu_alert_threshold = 80
        self.email_recipient = "test@gmail.com"
        self.is_monitoring = False
        self.monitoring_interval = 60  # seconds
        self.cpu_history = []  # Store CPU history as (timestamp, percent)
        self.history_max = 20  # Maximum number of history points to store

        # CSS styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            .critical { background-color: #FF6B6B; }
            .warning { background-color: #FFD166; }
            .normal { background-color: #06D6A0; }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Create main layout
        self.create_ui()

        # Initial memory & CPU check
        self.check_memory_cpu_once()

    def create_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)

        header_label = Gtk.Label(label="System Resource Monitor")
        header_label.set_markup("<span font_weight='bold' font_size='large'>System Resource Monitor</span>")
        main_box.pack_start(header_label, False, False, 10)

        # Create notebook for tabbed interface
        notebook = Gtk.Notebook()
        main_box.pack_start(notebook, True, True, 0)
        
        # Memory tab
        memory_box = self.create_memory_tab()
        notebook.append_page(memory_box, Gtk.Label(label="Memory"))
        
        # CPU tab
        cpu_box = self.create_cpu_tab()
        notebook.append_page(cpu_box, Gtk.Label(label="CPU"))
        
        # Settings tab
        settings_box = self.create_settings_tab()
        notebook.append_page(settings_box, Gtk.Label(label="Settings"))
        
        # Reports tab - NEW
        reports_box = self.create_reports_tab()
        notebook.append_page(reports_box, Gtk.Label(label="Reports"))

        # Control buttons
        button_box = Gtk.Box(spacing=5)
        main_box.pack_start(button_box, False, False, 10)
        
        self.start_button = Gtk.Button(label="Start Monitoring")
        self.start_button.connect("clicked", self.on_start_clicked)
        button_box.pack_start(self.start_button, True, True, 0)
        
        self.stop_button = Gtk.Button(label="Stop Monitoring")
        self.stop_button.connect("clicked", self.on_stop_clicked)
        self.stop_button.set_sensitive(False)
        button_box.pack_start(self.stop_button, True, True, 0)
        
        check_button = Gtk.Button(label="Check Now")
        check_button.connect("clicked", self.on_check_clicked)
        button_box.pack_start(check_button, True, True, 0)

        self.status_bar = Gtk.Statusbar()
        self.status_context = self.status_bar.get_context_id("status")
        main_box.pack_start(self.status_bar, False, False, 0)
        self.update_status("Ready")

    def create_memory_tab(self):
        memory_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        memory_box.set_border_width(10)

        frame = Gtk.Frame(label="Memory Usage")
        memory_box.pack_start(frame, False, False, 0)

        frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        frame_box.set_border_width(10)
        frame.add(frame_box)

        self.memory_progress_bar = Gtk.ProgressBar()
        self.memory_progress_bar.set_text("Memory Usage: 0%")
        self.memory_progress_bar.set_show_text(True)
        frame_box.pack_start(self.memory_progress_bar, False, False, 0)

        self.memory_details = Gtk.Label(label="Total: 0MB | Used: 0MB | Free: 0MB")
        frame_box.pack_start(self.memory_details, False, False, 0)

        threshold_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        memory_box.pack_start(threshold_box, False, False, 5)
        threshold_box.pack_start(Gtk.Label(label="Alert Threshold:"), False, False, 0)
        
        memory_adjustment = Gtk.Adjustment(value=self.memory_alert_threshold, lower=1, upper=100, step_increment=1)
        self.memory_threshold_spin = Gtk.SpinButton()
        self.memory_threshold_spin.set_adjustment(memory_adjustment)
        self.memory_threshold_spin.connect("value-changed", self.on_memory_threshold_changed)
        threshold_box.pack_start(self.memory_threshold_spin, False, False, 0)
        threshold_box.pack_start(Gtk.Label(label="%"), False, False, 0)

        return memory_box

    def create_cpu_tab(self):
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        cpu_box.set_border_width(10)

        # Current CPU usage frame
        current_frame = Gtk.Frame(label="Current CPU Usage")
        cpu_box.pack_start(current_frame, False, False, 0)

        current_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        current_box.set_border_width(10)
        current_frame.add(current_box)

        self.cpu_progress_bar = Gtk.ProgressBar()
        self.cpu_progress_bar.set_text("CPU Usage: 0%")
        self.cpu_progress_bar.set_show_text(True)
        current_box.pack_start(self.cpu_progress_bar, False, False, 0)

        self.cpu_details = Gtk.Label(label="Cores: 0 | Current: 0% | Load Avg: 0.00")
        current_box.pack_start(self.cpu_details, False, False, 0)
        
        threshold_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        cpu_box.pack_start(threshold_box, False, False, 5)
        threshold_box.pack_start(Gtk.Label(label="Alert Threshold:"), False, False, 0)
        
        cpu_adjustment = Gtk.Adjustment(value=self.cpu_alert_threshold, lower=1, upper=100, step_increment=1)
        self.cpu_threshold_spin = Gtk.SpinButton()
        self.cpu_threshold_spin.set_adjustment(cpu_adjustment)
        self.cpu_threshold_spin.connect("value-changed", self.on_cpu_threshold_changed)
        threshold_box.pack_start(self.cpu_threshold_spin, False, False, 0)
        threshold_box.pack_start(Gtk.Label(label="%"), False, False, 0)

        # CPU History frame
        history_frame = Gtk.Frame(label="CPU Usage History")
        cpu_box.pack_start(history_frame, True, True, 5)

        history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        history_box.set_border_width(10)
        history_frame.add(history_box)

        # Create a textview with monospace font for ASCII graph
        self.cpu_history_view = Gtk.TextView()
        self.cpu_history_view.set_editable(False)
        self.cpu_history_view.set_cursor_visible(False)
        self.cpu_history_view.override_font(Pango.FontDescription("monospace"))
        
        # Add scrollbar for history view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.cpu_history_view)
        scrolled_window.set_size_request(-1, 150)
        history_box.pack_start(scrolled_window, True, True, 0)

        return cpu_box

    def create_settings_tab(self):
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        settings_box.set_border_width(10)

        email_frame = Gtk.Frame(label="Email Alert Settings")
        settings_box.pack_start(email_frame, False, False, 0)

        email_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        email_box.set_border_width(10)
        email_frame.add(email_box)

        email_entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        email_box.pack_start(email_entry_box, False, False, 0)
        email_entry_box.pack_start(Gtk.Label(label="Alert Email:"), False, False, 0)
        self.email_entry = Gtk.Entry()
        self.email_entry.set_text(self.email_recipient)
        self.email_entry.connect("changed", self.on_email_changed)
        email_entry_box.pack_start(self.email_entry, True, True, 0)

        sender_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        email_box.pack_start(sender_box, False, False, 0)
        sender_box.pack_start(Gtk.Label(label="Sender Email:"), False, False, 0)
        self.sender_entry = Gtk.Entry()
        self.sender_entry.set_text("ketansayal04@gmail.com")
        sender_box.pack_start(self.sender_entry, True, True, 0)

        password_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        email_box.pack_start(password_box, False, False, 0)
        password_box.pack_start(Gtk.Label(label="App Password:"), False, False, 0)
        self.password_entry = Gtk.Entry()
        self.password_entry.set_visibility(False)
        self.password_entry.set_text("yoxu jkte qebl afzf")
        password_box.pack_start(self.password_entry, True, True, 0)

        # Monitor settings
        monitor_frame = Gtk.Frame(label="Monitoring Settings")
        settings_box.pack_start(monitor_frame, False, False, 10)
        
        monitor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        monitor_box.set_border_width(10)
        monitor_frame.add(monitor_box)
        
        interval_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        monitor_box.pack_start(interval_box, False, False, 0)
        interval_box.pack_start(Gtk.Label(label="Check Interval:"), False, False, 0)
        interval_adjustment = Gtk.Adjustment(value=self.monitoring_interval, lower=5, upper=3600, step_increment=5)
        self.interval_spin = Gtk.SpinButton()
        self.interval_spin.set_adjustment(interval_adjustment)
        self.interval_spin.connect("value-changed", self.on_interval_changed)
        interval_box.pack_start(self.interval_spin, False, False, 0)
        interval_box.pack_start(Gtk.Label(label="seconds"), False, False, 0)
        
        history_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        monitor_box.pack_start(history_box, False, False, 0)
        history_box.pack_start(Gtk.Label(label="History Points:"), False, False, 0)
        history_adjustment = Gtk.Adjustment(value=self.history_max, lower=5, upper=100, step_increment=5)
        self.history_spin = Gtk.SpinButton()
        self.history_spin.set_adjustment(history_adjustment)
        self.history_spin.connect("value-changed", self.on_history_changed)
        history_box.pack_start(self.history_spin, False, False, 0)
        history_box.pack_start(Gtk.Label(label="points"), False, False, 0)

        return settings_box
    
    def create_reports_tab(self):
        reports_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        reports_box.set_border_width(10)
        
        # Email report frame
        report_frame = Gtk.Frame(label="Email Report")
        reports_box.pack_start(report_frame, False, False, 0)
        
        report_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        report_box.set_border_width(10)
        report_frame.add(report_box)
        
        # Description label
        description = Gtk.Label()
        description.set_markup("<span>Request a detailed system resource report to be sent to your email</span>")
        description.set_line_wrap(True)
        report_box.pack_start(description, False, False, 5)
        
        # Email entry box
        email_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        report_box.pack_start(email_box, False, False, 5)
        
        email_box.pack_start(Gtk.Label(label="Recipient Email:"), False, False, 0)
        self.report_email_entry = Gtk.Entry()
        self.report_email_entry.set_placeholder_text("Enter your email address")
        email_box.pack_start(self.report_email_entry, True, True, 0)
        
        # Report options
        options_frame = Gtk.Frame(label="Report Options")
        report_box.pack_start(options_frame, False, False, 10)
        
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        options_box.set_border_width(10)
        options_frame.add(options_box)
        
        # Checkboxes for report content
        self.include_memory_check = Gtk.CheckButton(label="Include Memory Statistics")
        self.include_memory_check.set_active(True)
        options_box.pack_start(self.include_memory_check, False, False, 0)
        
        self.include_cpu_check = Gtk.CheckButton(label="Include CPU Statistics")
        self.include_cpu_check.set_active(True)
        options_box.pack_start(self.include_cpu_check, False, False, 0)
        
        self.include_history_check = Gtk.CheckButton(label="Include CPU History")
        self.include_history_check.set_active(True)
        options_box.pack_start(self.include_history_check, False, False, 0)
        
        self.include_system_info_check = Gtk.CheckButton(label="Include System Information")
        self.include_system_info_check.set_active(True)
        options_box.pack_start(self.include_system_info_check, False, False, 0)
        
        # Send button
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        report_box.pack_start(button_box, False, False, 10)
        
        send_report_button = Gtk.Button(label="Send Report")
        send_report_button.connect("clicked", self.on_send_report_clicked)
        button_box.pack_end(send_report_button, False, False, 0)
        
        # Schedule reports
        schedule_frame = Gtk.Frame(label="Schedule Reports")
        reports_box.pack_start(schedule_frame, False, False, 10)
        
        schedule_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        schedule_box.set_border_width(10)
        schedule_frame.add(schedule_box)
        
        self.schedule_check = Gtk.CheckButton(label="Send periodic reports")
        schedule_box.pack_start(self.schedule_check, False, False, 0)
        
        frequency_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        schedule_box.pack_start(frequency_box, False, False, 5)
        
        frequency_box.pack_start(Gtk.Label(label="Frequency:"), False, False, 0)
        
        self.frequency_combo = Gtk.ComboBoxText()
        self.frequency_combo.append_text("Hourly")
        self.frequency_combo.append_text("Daily")
        self.frequency_combo.append_text("Weekly")
        self.frequency_combo.set_active(1)  # Default to daily
        frequency_box.pack_start(self.frequency_combo, True, True, 0)
        
        return reports_box

    def get_memory_usage(self):
        try:
            cmd = "free | grep Mem | awk '{print $3/$2 * 100.0}' | cut -d. -f1"
            percent_used = int(subprocess.check_output(cmd, shell=True, text=True).strip())
            cmd = "free -m | grep Mem"
            mem_info = subprocess.check_output(cmd, shell=True, text=True).strip().split()
            total_mem = int(mem_info[1])
            used_mem = int(mem_info[2])
            free_mem = int(mem_info[3])
            return percent_used, total_mem, used_mem, free_mem
        except Exception as e:
            print(f"Error getting memory usage: {e}")
            return 0, 0, 0, 0

    def get_cpu_usage(self):
        try:
            # Get current CPU usage using top command (1 second sample)
            cmd = "top -bn2 -d 0.5 | grep '%Cpu' | tail -1 | awk '{print 100-$8}'"
            cpu_percent = float(subprocess.check_output(cmd, shell=True, text=True).strip())
            
            # Get CPU cores count
            cmd = "nproc"
            cpu_count = int(subprocess.check_output(cmd, shell=True, text=True).strip())
            
            # Get load average
            cmd = "cat /proc/loadavg | awk '{print $1}'"
            load_avg = float(subprocess.check_output(cmd, shell=True, text=True).strip())
            
            # Add to history
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.cpu_history.append((timestamp, cpu_percent))
            
            # Keep only the latest history_max entries
            while len(self.cpu_history) > self.history_max:
                self.cpu_history.pop(0)
                
            return cpu_percent, cpu_count, load_avg
        except Exception as e:
            print(f"Error getting CPU usage: {e}")
            return 0, 0, 0.0
            
    def get_system_info(self):
        try:
            # Get OS information
            cmd = "lsb_release -d | cut -f2"
            os_info = subprocess.check_output(cmd, shell=True, text=True).strip()
            
            # Get kernel version
            cmd = "uname -r"
            kernel = subprocess.check_output(cmd, shell=True, text=True).strip()
            
            # Get uptime
            cmd = "uptime -p"
            uptime = subprocess.check_output(cmd, shell=True, text=True).strip()
            
            # Get hostname
            cmd = "hostname"
            hostname = subprocess.check_output(cmd, shell=True, text=True).strip()
            
            return {
                "os": os_info,
                "kernel": kernel,
                "uptime": uptime,
                "hostname": hostname
            }
        except Exception as e:
            print(f"Error getting system info: {e}")
            return {
                "os": "Unknown",
                "kernel": "Unknown",
                "uptime": "Unknown",
                "hostname": "Unknown"
            }

    def update_cpu_history_graph(self):
        if not self.cpu_history:
            return
            
        buffer = self.cpu_history_view.get_buffer()
        buffer.set_text("")
        
        # Create ASCII graph
        graph_height = 10  # rows for the graph
        graph_text = "CPU Usage History:\n"
        
        # Create Y-axis labels
        for i in range(graph_height, -1, -1):
            y_value = int((i / graph_height) * 100)
            if i == graph_height:
                graph_text += f"{y_value:3d}% ┌"
            elif i == 0:
                graph_text += f"{y_value:3d}% └"
            else:
                graph_text += f"{y_value:3d}% │"
                
            # Add data points
            for timestamp, value in self.cpu_history:
                scaled_value = (value / 100) * graph_height
                if round(scaled_value) == i:
                    graph_text += "●"
                elif scaled_value > i:
                    graph_text += "│"
                else:
                    graph_text += " "
            
            graph_text += "\n"
            
        # Add x-axis
        graph_text += "     "
        for i in range(len(self.cpu_history)):
            if i % 5 == 0:  # Show timestamp every 5 points
                graph_text += "┴"
            else:
                graph_text += "─"
        graph_text += "\n"
        
        # Add timestamp labels
        graph_text += "     "
        for i in range(len(self.cpu_history)):
            if i % 5 == 0:  # Show timestamp every 5 points
                graph_text += self.cpu_history[i][0][3:5]  # Minutes
            else:
                graph_text += "  "
                
        buffer.set_text(graph_text)
        return graph_text

    def check_memory_cpu_once(self):
        # Get memory stats
        mem_percent, total_mem, used_mem, free_mem = self.get_memory_usage()
        
        # Get CPU stats
        cpu_percent, cpu_count, load_avg = self.get_cpu_usage()
        
        # Update UI
        GLib.idle_add(self.update_memory_ui, mem_percent, total_mem, used_mem, free_mem)
        GLib.idle_add(self.update_cpu_ui, cpu_percent, cpu_count, load_avg)
        
        # Check for alerts
        if mem_percent >= self.memory_alert_threshold:
            GLib.idle_add(self.send_alert, "Memory", mem_percent, self.memory_alert_threshold)
            
        if cpu_percent >= self.cpu_alert_threshold:
            GLib.idle_add(self.send_alert, "CPU", cpu_percent, self.cpu_alert_threshold)
            
        return True

    def update_memory_ui(self, percent_used, total_mem, used_mem, free_mem):
        self.memory_progress_bar.set_fraction(percent_used / 100.0)
        self.memory_progress_bar.set_text(f"Memory Usage: {percent_used}%")
        self.memory_details.set_text(f"Total: {total_mem}MB | Used: {used_mem}MB | Free: {free_mem}MB")
        
        style_context = self.memory_progress_bar.get_style_context()
        style_context.remove_class("normal")
        style_context.remove_class("warning")
        style_context.remove_class("critical")
        
        if percent_used >= self.memory_alert_threshold:
            style_context.add_class("critical")
        elif percent_used >= 70:
            style_context.add_class("warning")
        else:
            style_context.add_class("normal")
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.update_status(f"Last updated: {current_time}")

    def update_cpu_ui(self, cpu_percent, cpu_count, load_avg):
        self.cpu_progress_bar.set_fraction(cpu_percent / 100.0)
        self.cpu_progress_bar.set_text(f"CPU Usage: {cpu_percent:.1f}%")
        self.cpu_details.set_text(f"Cores: {cpu_count} | Current: {cpu_percent:.1f}% | Load Avg: {load_avg:.2f}")
        
        style_context = self.cpu_progress_bar.get_style_context()
        style_context.remove_class("normal")
        style_context.remove_class("warning")
        style_context.remove_class("critical")
        
        if cpu_percent >= self.cpu_alert_threshold:
            style_context.add_class("critical")
        elif cpu_percent >= 60:
            style_context.add_class("warning")
        else:
            style_context.add_class("normal")
            
        # Update CPU history graph
        self.update_cpu_history_graph()

    def send_alert(self, resource_type, percent_used, threshold):
        try:
            sender_email = self.sender_entry.get_text()
            app_password = self.password_entry.get_text()
            receiver_email = self.email_recipient

            subject = f"ALERT: {resource_type} usage at {percent_used:.1f}%"
            body = f"⚠️ Your system {resource_type.lower()} usage is at {percent_used:.1f}%, which exceeds the threshold of {threshold}%."

            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = receiver_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
            server.quit()

            self.update_status(f"✅ Email alert sent to {receiver_email}")

            dialog = Gtk.MessageDialog(
                transient_for=self,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=f"{resource_type} Alert"
            )
            dialog.format_secondary_text(body)
            dialog.run()
            dialog.destroy()

        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            self.update_status("❌ Failed to send email")
            
    def generate_report(self):
        """Generate a comprehensive system resource report"""
        report = []
        report.append("=" * 50)
        report.append("SYSTEM RESOURCE REPORT")
        report.append("=" * 50)
        report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Add system info if selected
        if self.include_system_info_check.get_active():
            system_info = self.get_system_info()
            report.append("-" * 50)
            report.append("SYSTEM INFORMATION")
            report.append("-" * 50)
            report.append(f"Hostname: {system_info['hostname']}")
            report.append(f"Operating System: {system_info['os']}")
            report.append(f"Kernel Version: {system_info['kernel']}")
            report.append(f"System Uptime: {system_info['uptime']}")
            report.append("")
        
        # Add memory stats if selected
        if self.include_memory_check.get_active():
            mem_percent, total_mem, used_mem, free_mem = self.get_memory_usage()
            report.append("-" * 50)
            report.append("MEMORY STATISTICS")
            report.append("-" * 50)
            report.append(f"Memory Usage: {mem_percent}%")
            report.append(f"Total Memory: {total_mem} MB")
            report.append(f"Used Memory: {used_mem} MB")
            report.append(f"Free Memory: {free_mem} MB")
            if mem_percent >= self.memory_alert_threshold:
                report.append(f"⚠️ ALERT: Memory usage exceeds threshold of {self.memory_alert_threshold}%")
            report.append("")
        
        # Add CPU stats if selected
        if self.include_cpu_check.get_active():
            cpu_percent, cpu_count, load_avg = self.get_cpu_usage()
            report.append("-" * 50)
            report.append("CPU STATISTICS")
            report.append("-" * 50)
            report.append(f"Current CPU Usage: {cpu_percent:.1f}%")
            report.append(f"CPU Cores: {cpu_count}")
            report.append(f"Load Average: {load_avg:.2f}")
            if cpu_percent >= self.cpu_alert_threshold:
                report.append(f"⚠️ ALERT: CPU usage exceeds threshold of {self.cpu_alert_threshold}%")
            report.append("")
        
        # Add CPU history if selected
        if self.include_history_check.get_active() and self.cpu_history:
            report.append("-" * 50)
            report.append("CPU USAGE HISTORY")
            report.append("-" * 50)
            for i, (timestamp, value) in enumerate(self.cpu_history):
                report.append(f"{timestamp}: {value:.1f}%")
            report.append("")
            
            # Add ASCII graph
            graph_text = self.update_cpu_history_graph()
            # Add CPU graph to report if there is data
        if graph_text:
            report.append("ASCII CPU Usage Graph:")
            report.append("")
            for line in graph_text.split('\n'):
                report.append(line)
            report.append("")
        
        report.append("=" * 50)
        report.append("END OF REPORT")
        report.append("=" * 50)
        
        return "\n".join(report)
    
    def on_send_report_clicked(self, button):
        """Send the system resource report to the specified email"""
        email = self.report_email_entry.get_text()
        if not email:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Email Required"
            )
            dialog.format_secondary_text("Please enter an email address to send the report to.")
            dialog.run()
            dialog.destroy()
            return
            
        try:
            sender_email = self.sender_entry.get_text()
            app_password = self.password_entry.get_text()
            receiver_email = email
            
            subject = f"System Resource Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            body = self.generate_report()
            
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = receiver_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
            server.quit()
            
            self.update_status(f"✅ Report sent to {receiver_email}")
            
            dialog = Gtk.MessageDialog(
                transient_for=self,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Report Sent"
            )
            dialog.format_secondary_text(f"System resource report successfully sent to {receiver_email}")
            dialog.run()
            dialog.destroy()
            
        except Exception as e:
            print(f"❌ Failed to send report: {e}")
            self.update_status("❌ Failed to send report")
            
            dialog = Gtk.MessageDialog(
                transient_for=self,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Failed to Send Report"
            )
            dialog.format_secondary_text(f"Error: {str(e)}")
            dialog.run()
            dialog.destroy()
    
    def update_status(self, message):
        """Update the status bar with a message"""
        self.status_bar.pop(self.status_context)
        self.status_bar.push(self.status_context, message)
    
    def on_memory_threshold_changed(self, spin_button):
        """Handle memory threshold change"""
        self.memory_alert_threshold = spin_button.get_value_as_int()
    
    def on_cpu_threshold_changed(self, spin_button):
        """Handle CPU threshold change"""
        self.cpu_alert_threshold = spin_button.get_value_as_int()
    
    def on_email_changed(self, entry):
        """Handle email recipient change"""
        self.email_recipient = entry.get_text()
    
    def on_interval_changed(self, spin_button):
        """Handle monitoring interval change"""
        self.monitoring_interval = spin_button.get_value_as_int()
    
    def on_history_changed(self, spin_button):
        """Handle history size change"""
        self.history_max = spin_button.get_value_as_int()
        
        # Trim history if needed
        while len(self.cpu_history) > self.history_max:
            self.cpu_history.pop(0)
        
        # Update the graph
        self.update_cpu_history_graph()
    
    def on_check_clicked(self, button):
        """Handle manual check button click"""
        threading.Thread(target=self.check_memory_cpu_once).start()
        self.update_status("Checking system resources...")
    
    def on_start_clicked(self, button):
        """Start monitoring"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.start_button.set_sensitive(False)
            self.stop_button.set_sensitive(True)
            self.update_status("Monitoring started")
            
            # Start monitoring in a separate thread
            self.monitoring_thread = threading.Thread(target=self.monitor_resources)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
    
    def on_stop_clicked(self, button):
        """Stop monitoring"""
        if self.is_monitoring:
            self.is_monitoring = False
            self.start_button.set_sensitive(True)
            self.stop_button.set_sensitive(False)
            self.update_status("Monitoring stopped")
    
    def monitor_resources(self):
        """Monitor resources at regular intervals"""
        while self.is_monitoring:
            self.check_memory_cpu_once()
            time.sleep(self.monitoring_interval)

if __name__ == "__main__":
    window = MemoryCpuMonitorWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()