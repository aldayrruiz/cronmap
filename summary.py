from lxml import etree
import os

class SummaryGenerator:
    def __init__(self, output_dir="results"):
        self.output_dir = output_dir

    def generate_port_summary(self, separator=","):
        """
        Genera un resumen de IPs y puertos encontrados desde merged.xml.
        Formato:
        Target: 10.10.10.10
        Ports: 1,2,3,4,5,6
        
        Target: 10.10.10.11
        Ports: 1,2,3,4,5,6
        """
        merged_xml = os.path.join(self.output_dir, "merged.xml")
        
        if not os.path.exists(merged_xml):
            print("Error: No se encontró el archivo merged.xml")
            return None
        
        try:
            tree = etree.parse(merged_xml)
            root = tree.getroot()
            
            targets_dict = {}
            
            # Extraer hosts y sus puertos
            for host in root.findall("host"):
                addr = host.find("address")
                if addr is None:
                    continue
                
                ip = addr.get("addr")
                ports = []
                
                # Buscar puertos abiertos
                ports_elem = host.find("ports")
                if ports_elem is not None:
                    for port in ports_elem.findall("port"):
                        state = port.find("state")
                        if state is not None and state.get("state") == "open":
                            port_num = port.get("protocol") + "/" + port.get("portid")
                            ports.append(int(port.get("portid")))
                
                if ports:
                    ports.sort()
                    targets_dict[ip] = ports
            
            # Generar salida
            if not targets_dict:
                print("No se encontraron puertos abiertos.")
                return ""
            
            output_lines = []
            for ip in sorted(targets_dict.keys()):
                ports_str = separator.join(str(p) for p in targets_dict[ip])
                output_lines.append(f"Target: {ip}")
                output_lines.append(f"Ports: {ports_str}")
                output_lines.append("")
            
            result = "\n".join(output_lines).strip()
            return result
            
        except Exception as e:
            print(f"Error al procesar merged.xml: {e}")
            return None