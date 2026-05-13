#!/usr/bin/env python3

from lxml import etree
from glob import glob
from copy import deepcopy
from datetime import datetime
import os
import subprocess

class HtmlGenerator:
    def __init__(self, output_dir="results"):
        self.output_dir = output_dir

    def merge_xml_files(self):
        """
        Merge múltiples archivos XML de nmap en un único archivo.
        Recalcula correctamente los totales y sincroniza la información de escaneo.
        Incluye TODAS las IPs escaneadas en el atributo args.
        """
        from glob import glob
        import re
        
        xml_files = sorted(glob(os.path.join(self.output_dir, "scan_*.xml")))
        
        if not xml_files:
            print("Error: No se encontraron archivos XML para fusionar.")
            return None
        
        # Parse first file as base
        base_tree = etree.parse(xml_files[0])
        base_root = base_tree.getroot()
        
        # Collect all hosts from all files and all IPs
        all_hosts = []
        earliest_start = None
        latest_end = None
        all_ips = []
        nmap_args_base = None
        
        for xml_file in xml_files:
            tree = etree.parse(xml_file)
            root = tree.getroot()
            
            # Collect hosts
            for host in root.findall("host"):
                all_hosts.append(deepcopy(host))
            
            # Track earliest start time
            nmaprun_start = root.get("start")
            if nmaprun_start and (earliest_start is None or int(nmaprun_start) < int(earliest_start)):
                earliest_start = nmaprun_start
            
            # Track latest end time from runstats
            runstats = root.find("runstats")
            if runstats is not None:
                finished = runstats.find("finished")
                if finished is not None:
                    end_time = finished.get("time")
                    if end_time and (latest_end is None or int(end_time) > int(latest_end)):
                        latest_end = end_time
            
            # Extract IPs from nmaprun args
            args = root.get("args", "")
            if not nmap_args_base:
                # Extract the base command (everything up to the IPs)
                # Typically: nmap [options] -oX results/scan_N.xml [IPs]
                match = re.match(r'(.*?-oX\s+\S+\s+)', args)
                if match:
                    nmap_args_base = match.group(1).strip()
            
            # Extract all IPs from this file
            ips = re.findall(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', args)
            # ips = re.findall(r'192\.168\.\d+\.\d+', args)
            all_ips.extend(ips)
        
        # Remove old runstats and hosts from base
        runstats_old = base_root.find("runstats")
        if runstats_old is not None:
            base_root.remove(runstats_old)
        
        for host in base_root.findall("host"):
            base_root.remove(host)
        
        # Add all collected hosts
        for host in all_hosts:
            base_root.append(host)
        
        # Calculate host statistics
        hosts_up = sum(1 for host in all_hosts if host.find("status").get("state") == "up")
        hosts_down = len(all_hosts) - hosts_up
        hosts_total = len(all_hosts)
        
        # Update nmaprun attributes
        if earliest_start:
            base_root.set("start", earliest_start)
            start_dt = datetime.fromtimestamp(int(earliest_start))
            base_root.set("startstr", start_dt.strftime("%a %b %d %H:%M:%S %Y"))
        
        # Build the merged args with all IPs
        merged_ips_str = " ".join(all_ips)
        if nmap_args_base:
            merged_args = f"{nmap_args_base} {merged_ips_str}"
        else:
            merged_args = f"nmap -oX {os.path.join(self.output_dir, 'merged.xml')} {merged_ips_str}"
        
        base_root.set("args", merged_args)
        
        # Create new runstats
        runstats = etree.Element("runstats")
        finished = etree.SubElement(runstats, "finished")
        finished.set("time", latest_end or str(int(datetime.now().timestamp())))
        finished.set("timestr", datetime.fromtimestamp(int(latest_end or str(int(datetime.now().timestamp())))).strftime("%a %b %d %H:%M:%S %Y"))
        
        elapsed = int(latest_end or str(int(datetime.now().timestamp()))) - int(earliest_start or str(int(datetime.now().timestamp())))
        finished.set("elapsed", str(elapsed))
        finished.set("summary", f"Nmap done; {len(all_ips)} IP addresses ({hosts_up} host{'s' if hosts_up != 1 else ''} up) scanned")
        finished.set("exit", "success")
        
        hosts_elem = etree.SubElement(runstats, "hosts")
        hosts_elem.set("up", str(hosts_up))
        hosts_elem.set("down", str(hosts_down))
        hosts_elem.set("total", str(hosts_total))
        
        base_root.append(runstats)
        
        # Save merged XML
        merged_path = os.path.join(self.output_dir, "merged.xml")
        base_tree.write(
            merged_path,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8"
        )
        
        print(f"[+] Fusión completada: {hosts_total} hosts ({hosts_up} activos, {hosts_down} inactivos)")
        print(f"[+] Total IPs escaneadas: {len(all_ips)}")
        return merged_path

    def generate_html_report(self):
        """
        Genera un reporte HTML a partir del XML fusionado usando xsltproc.
        """
        output_dir = self.output_dir
        merged_xml = os.path.join(output_dir, "merged.xml")
        output_html = os.path.join(output_dir, "results.html")
        
        # First, merge the XML files
        print("Fusionando archivos XML...")
        self.merge_xml_files()
        
        if not os.path.exists(merged_xml):
            print("Error: No se encontró el archivo merged.xml")
            return False
        
        # Generate HTML using xsltproc
        print("Generando reporte HTML...")
        try:
            cmd = ["xsltproc", merged_xml, "-o", output_html]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode == 0:
                print(f"[+] Reporte HTML generado: {output_html}")
                return True
            else:
                print(f"Error al generar HTML: {result.stderr}")
                return False
        except FileNotFoundError:
            print("Error: xsltproc no está instalado. Instálalo con: sudo apt-get install xsltproc")
            return False
