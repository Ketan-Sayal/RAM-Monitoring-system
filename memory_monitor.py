#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, Pango
import subprocess
import threading
import time
from datetime import datetime

class MemoryMonitorWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Memory Monitor")
        self.set_border_width(10)
        self.set_default_size(500, 350)
        
        # Default settings
        self.alert_threshold = 90
        self.email_recipient = "test@gmail.com"
        self.is_monitoring = False
        self.monitoring_interval = 60  # seconds
        
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
        
        # Initial memory check
        self.check_memory_once()
    
    def create_ui(self):
        # Main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(main_box)
        
        # Header
        header_label = Gtk.Label(label="System Memory Monitor")
        header_label.set_markup("<span font_weight='bold' font_size='large'>System Memory Monitor</span>")
        main_box.pack_start(header_label, False, False, 10)
        
        # Memory usage frame
        frame = Gtk.Frame(label="Memory Usage")
        main_box.pack_start(frame, False, False, 0)
        
        frame_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        frame_box.set_border_width(10)
        frame.add(frame_box)
        
        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_text("Memory Usage: 0%")
        self.progress_bar.set_show_text(True)
        frame_box.pack_start(self.progress_bar, False, False, 0)
        
        # Memory details
        self.memory_details = Gtk.Label(label="Total: 0MB | Used: 0MB | Free: 0MB")
        frame_box.pack_start(self.memory_details, False, False, 0)
        
        # Settings frame
        settings_frame = Gtk.Frame(label="Settings")
        main_box.pack_start(settings_frame, False, False, 0)
        
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        settings_box.set_border_width(10)
        settings_frame.add(settings_box)
        
        # Threshold setting
        threshold_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        settings_box.pack_start(threshold_box, False, False, 0)
        
        threshold_box.pack_start(Gtk.Label(label="Alert Threshold:"), False, False, 0)
        
        adjustment = Gtk.Adjustment(value=self.alert_threshold, lower=1, upper=100, step_increment=1)
        self.threshold_spin = Gtk.SpinButton()
        self.threshold_spin.set_adjustment(adjustment)
        self.threshold_spin.connect("value-changed", self.on_threshold_changed)
        threshold_box.pack_start(self.threshold_spin, False, False, 0)
        
        threshold_box.pack_start(Gtk.Label(label="%"), False, False, 0)
        
        # Email setting
        email_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        settings_box.pack_start(email_box, False, False, 0)
        
        email_box.pack_start(Gtk.Label(label="Alert Email:"), False, False, 0)
        
        self.email_entry = Gtk.Entry()
        self.email_entry.set_text(self.email_recipient)
        self.email_entry.connect("changed", self.on_email_changed)
        email_box.pack_start(self.email_entry, True, True, 0)
        
        # Interval setting 
        interval_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        settings_box.pack_start(interval_box, False, False, 0)
        
        interval_box.pack_start(Gtk.Label(label="Check Interval:"), False, False, 0)
        
        interval_adjustment = Gtk.Adjustment(value=self.monitoring_interval, lower=10, upper=3600, step_increment=10)
        self.interval_spin = Gtk.SpinButton()
        self.interval_spin.set_adjustment(interval_adjustment)
        self.interval_spin.connect("value-changed", self.on_interval_changed)
        interval_box.pack_start(self.interval_spin, False, False, 0)
        
        interval_box.pack_start(Gtk.Label(label="seconds"), False, False, 0)
        
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
        
        # Status bar
        self.status_bar = Gtk.Statusbar()
        self.status_context = self.status_bar.get_context_id("status")
        main_box.pack_start(self.status_bar, False, False, 0)
        self.update_status("Ready")
    
    def get_memory_usage(self):
        try:
            # Get memory usage percentage
            cmd = "free | grep Mem | awk '{print $3/$2 * 100.0}' | cut -d. -f1"
            percent_used = int(subprocess.check_output(cmd, shell=True, text=True).strip())
            
            # Get detailed memory info
            cmd = "free -m | grep Mem"
            mem_info = subprocess.check_output(cmd, shell=True, text=True).strip().split()
            total_mem = int(mem_info[1])
            used_mem = int(mem_info[2])
            free_mem = int(mem_info[3])
            
            return percent_used, total_mem, used_mem, free_mem
        except Exception as e:
            print(f"Error getting memory usage: {e}")
            return 0, 0, 0, 0
    
    def check_memory_once(self):
        percent_used, total_mem, used_mem, free_mem = self.get_memory_usage()
        
        # Update UI (needs to be on main thread)
        GLib.idle_add(self.update_ui, percent_used, total_mem, used_mem, free_mem)
        
        # Check for alert condition
        if percent_used >= self.alert_threshold:
            GLib.idle_add(self.send_alert, percent_used)
        
        return True
    
    def update_ui(self, percent_used, total_mem, used_mem, free_mem):
        # Update progress bar
        self.progress_bar.set_fraction(percent_used / 100.0)
        self.progress_bar.set_text(f"Memory Usage: {percent_used}%")
        
        # Update memory details
        self.memory_details.set_text(f"Total: {total_mem}MB | Used: {used_mem}MB | Free: {free_mem}MB")
        
        # Update progress bar style based on memory usage
        style_context = self.progress_bar.get_style_context()
        style_context.remove_class("normal")
        style_context.remove_class("warning")
        style_context.remove_class("critical")
        
        if percent_used >= self.alert_threshold:
            style_context.add_class("critical")
        elif percent_used >= 70:
            style_context.add_class("warning")
        else:
            style_context.add_class("normal")
        
        # Update timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.update_status(f"Last updated: {current_time}")
    
    def send_alert(self, percent_used):
        # Create a dialog for the alert
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="Memory Alert"
        )
        dialog.format_secondary_text(f"System memory usage is at {percent_used}%, which exceeds the threshold of {self.alert_threshold}%")
        dialog.run()
        dialog.destroy()
        
        # Send email alert using the mail command
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            email_cmd = f'echo "Low memory on server as on {current_time}" | mail -s "Alert: Server running low on memory {percent_used}%" {self.email_recipient}'
            subprocess.run(email_cmd, shell=True)
            self.update_status(f"Email alert sent to {self.email_recipient}")
        except Exception as e:
            print(f"Failed to send email: {e}")
            self.update_status(f"Failed to send email alert: {e}")
    
    def update_status(self, message):
        self.status_bar.pop(self.status_context)
        self.status_bar.push(self.status_context, message)
    
    def on_check_clicked(self, button):
        threading.Thread(target=self.check_memory_once, daemon=True).start()
    
    def on_threshold_changed(self, spin):
        self.alert_threshold = spin.get_value_as_int()
    
    def on_email_changed(self, entry):
        self.email_recipient = entry.get_text()
    
    def on_interval_changed(self, spin):
        self.monitoring_interval = spin.get_value_as_int()
        if self.is_monitoring:
            # Restart monitoring with new interval
            self.on_stop_clicked(None)
            self.on_start_clicked(None)
    
    def on_start_clicked(self, button):
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
            self.monitor_thread.start()
            
            self.start_button.set_sensitive(False)
            self.stop_button.set_sensitive(True)
            self.update_status(f"Monitoring active - checking every {self.monitoring_interval} seconds")
    
    def on_stop_clicked(self, button):
        self.is_monitoring = False
        self.start_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        self.update_status("Monitoring stopped")
    
    def monitoring_loop(self):
        while self.is_monitoring:
            self.check_memory_once()
            time.sleep(self.monitoring_interval)

if __name__ == "__main__":
    win = MemoryMonitorWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()