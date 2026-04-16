from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str

log = core.getLogger()

class PortMonitor (object):
    def __init__ (self):
        core.openflow.addListeners(self)
        self.mac_to_port = {}  # Learning switch table

    def _handle_PortStatus (self, event):
        """Detect port up/down events and log changes."""
        port_no = event.port
        switch_id = dpid_to_str(event.dpid)
        
        if event.added:
            log.info("--- ALERT --- [Switch %s] Port %s was ADDED", switch_id, port_no)
        elif event.deleted:
            log.warning("--- ALERT --- [Switch %s] Port %s was DELETED", switch_id, port_no)
        elif event.modified:
            is_down = event.ofp.desc.state & of.OFPPS_LINK_DOWN
            status = "DOWN" if is_down else "UP"
            if is_down:
                log.error("--- ALERT --- [Switch %s] Port %s is %s", switch_id, port_no, status)
            else:
                log.info("--- ALERT --- [Switch %s] Port %s is %s", switch_id, port_no, status)

    def _handle_PacketIn (self, event):
        """Handle packet_in and install explicit flow rules (match+action)."""
        packet = event.parsed
        if not packet.parsed: return
        
        self.mac_to_port[packet.src] = event.port # Learn source MAC

        if packet.dst in self.mac_to_port:
            out_port = self.mac_to_port[packet.dst]
            
            # MATCH-ACTION: Create flow rule for this connection
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet)
            msg.actions.append(of.ofp_action_output(port = out_port))
            event.connection.send(msg)
            
            # Send the current packet out immediately
            msg_packet = of.ofp_packet_out()
            msg_packet.data = event.ofp
            msg_packet.actions.append(of.ofp_action_output(port = out_port))
            event.connection.send(msg_packet)
        else:
            # Flood if destination is unknown
            msg = of.ofp_packet_out(data = event.ofp, action = of.ofp_action_output(port = of.OFPP_FLOOD))
            event.connection.send(msg)

def launch ():
    core.registerNew(PortMonitor)
    log.info("Port Monitoring Tool Started.")
