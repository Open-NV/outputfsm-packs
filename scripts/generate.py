#!/usr/bin/env python3
"""Generate the reviewed v1 catalog into one YAML definition per command.

The declarative command matrix below is the source of truth.  Generated files
are committed so downstream consumers never need this script at runtime.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from string import Template
from typing import Any
import shutil
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from outputfsm_packs.engine import normalized_result, render  # noqa: E402


class LiteralSafeDumper(yaml.SafeDumper):
    """Emit multiline templates and fixtures as readable YAML literal blocks."""


def _represent_string(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


LiteralSafeDumper.add_representer(str, _represent_string)


# var, inventory path, healthy value, JSON-ish type, normalized result path,
# human-readable CLI label, optional presentation generator
CATEGORIES: dict[str, dict[str, Any]] = {
    "system_version": {
        "fields": [
            ("os_version", "system.os_version", "17.12.4-open", "string", "system.os_version", "Software version", None),
            ("image", "system.image", "open-synthetic-image.bin", "string", "system.image", "Image", None),
            ("uptime", "system.uptime_seconds", 987654, "integer", "system.uptime_seconds", "Uptime", "uptime_human"),
            ("oper_state", "system.oper_state", "up", "string", "system.oper_state", "Operating state", None),
        ],
        "validation": ("system.oper_state", "eq", "up", "down"),
    },
    "interface_summary": {
        "fields": [
            ("total", "interfaces.total", 48, "integer", "interfaces.total", "Interfaces", None),
            ("up", "interfaces.up", 47, "integer", "interfaces.up", "Up", None),
            ("down", "interfaces.down", 1, "integer", "interfaces.down", "Down", None),
        ],
        "validation": ("interfaces.down", "lte", 1, 6),
    },
    "interface_detail": {
        "fields": [
            ("error_count", "interfaces.error_count", 0, "integer", "interfaces.error_count", "Input/output errors", None),
            ("utilization", "interfaces.utilization_pct", 31.2, "number", "interfaces.utilization_pct", "Peak utilization", "percent"),
            ("mtu", "interfaces.mtu", 1500, "integer", "interfaces.mtu", "MTU", None),
        ],
        "validation": ("interfaces.error_count", "lte", 0, 14),
    },
    "routes": {
        "fields": [
            ("route_total", "routes.total", 128, "integer", "routes.total", "Routes", None),
            ("default_present", "routes.default_present", True, "boolean", "routes.default_present", "Default route present", "yes_no"),
            ("stale", "routes.stale", 0, "integer", "routes.stale", "Stale routes", None),
        ],
        "validation": ("routes.default_present", "eq", True, False),
    },
    "arp": {
        "fields": [
            ("entries", "arp.entries", 96, "integer", "arp.entries", "ARP/neighbor entries", None),
            ("incomplete", "arp.incomplete", 0, "integer", "arp.incomplete", "Incomplete entries", None),
        ],
        "validation": ("arp.incomplete", "eq", 0, 5),
    },
    "mac": {
        "fields": [
            ("entries", "mac.entries", 742, "integer", "mac.entries", "MAC entries", None),
            ("dynamic", "mac.dynamic", 736, "integer", "mac.dynamic", "Dynamic entries", None),
        ],
        "validation": ("mac.entries", "gte", 1, 0),
    },
    "neighbors": {
        "fields": [
            ("count", "neighbors.count", 6, "integer", "neighbors.count", "Discovered neighbors", None),
            ("expected", "neighbors.expected_count", 6, "integer", "neighbors.expected_count", "Expected neighbors", None),
            ("expected_matches", "neighbors.expected_matches", True, "boolean", "neighbors.expected_matches", "Expected set matched", "yes_no"),
        ],
        "validation": ("neighbors.expected_matches", "eq", True, False),
    },
    "vlans": {
        "fields": [
            ("total", "vlans.total", 24, "integer", "vlans.total", "VLANs", None),
            ("active", "vlans.active", 24, "integer", "vlans.active", "Active VLANs", None),
        ],
        "validation": ("vlans.active", "gte", 1, 0),
    },
    "aggregation": {
        "fields": [
            ("total", "aggregation.total", 4, "integer", "aggregation.total", "Aggregates", None),
            ("up", "aggregation.up", 4, "integer", "aggregation.up", "Operational aggregates", None),
            ("down", "aggregation.down", 0, "integer", "aggregation.down", "Down aggregates", None),
        ],
        "validation": ("aggregation.down", "eq", 0, 2),
    },
    "routing_peers": {
        "fields": [
            ("peers", "routing.peers_total", 8, "integer", "routing.peers_total", "Peers", None),
            ("established", "routing.peers_established", 8, "integer", "routing.peers_established", "Established", None),
            ("ratio", "routing.established_ratio_pct", 100.0, "number", "routing.established_ratio_pct", "Established ratio", "percent"),
        ],
        "validation": ("routing.established_ratio_pct", "gte", 95, 62.5),
    },
    "redundancy": {
        "fields": [
            ("state", "redundancy.state", "active", "string", "redundancy.state", "Local state", None),
            ("peer", "redundancy.peer_state", "standby-ready", "string", "redundancy.peer_state", "Peer state", None),
            ("ready", "redundancy.ready", True, "boolean", "redundancy.ready", "Redundancy ready", "yes_no"),
        ],
        "validation": ("redundancy.ready", "eq", True, False),
    },
    "hardware": {
        "fields": [
            ("modules", "hardware.modules_total", 3, "integer", "hardware.modules_total", "Modules/components", None),
            ("ok", "hardware.modules_ok", 3, "integer", "hardware.modules_ok", "Healthy components", None),
            ("faulty", "hardware.faulty_modules", 0, "integer", "hardware.faulty_modules", "Faulty components", None),
        ],
        "validation": ("hardware.faulty_modules", "eq", 0, 1),
    },
    "environment": {
        "fields": [
            ("temperature", "environment.temp_c", 39.5, "number", "environment.temp_c", "Peak temperature C", None),
            ("fans_ok", "environment.fans_ok", True, "boolean", "environment.fans_ok", "Fans healthy", "yes_no"),
            ("psus_ok", "environment.psus_ok", True, "boolean", "environment.psus_ok", "Power supplies healthy", "yes_no"),
        ],
        "validation": ("environment.temp_c", "lte", 75, 93.0),
    },
    "cpu": {
        "fields": [
            ("cpu", "resources.cpu_pct", 22.4, "number", "resources.cpu_pct", "CPU utilization", "percent"),
            ("load", "resources.load_5m", 0.42, "number", "resources.load_5m", "Five-minute load", None),
        ],
        "validation": ("resources.cpu_pct", "lte", 80, 98.1),
    },
    "memory": {
        "fields": [
            ("memory", "resources.memory_used_pct", 48.7, "number", "resources.memory_used_pct", "Memory used", "percent"),
            ("free_mb", "resources.memory_free_mb", 4096, "integer", "resources.memory_free_mb", "Memory free MB", None),
        ],
        "validation": ("resources.memory_used_pct", "lte", 85, 97.0),
    },
    "logging": {
        "fields": [
            ("critical", "logging.critical_count", 0, "integer", "logging.critical_count", "Critical messages", None),
            ("warnings", "logging.warning_count", 2, "integer", "logging.warning_count", "Warning messages", None),
            ("last_event", "logging.last_event", "synthetic health event", "string", "logging.last_event", "Last event", None),
        ],
        "validation": ("logging.critical_count", "eq", 0, 4),
    },
    "clock": {
        "fields": [
            ("clock", "clock.iso8601", "2026-08-16T07:00:00Z", "string", "clock.iso8601", "Clock", None),
            ("synced", "clock.synced", True, "boolean", "clock.synced", "Time synchronized", "yes_no"),
            ("offset", "clock.offset_ms", 1.4, "number", "clock.offset_ms", "Offset ms", None),
        ],
        "validation": ("clock.synced", "eq", True, False),
    },
    "inventory": {
        "fields": [
            ("components", "inventory_state.components", 7, "integer", "inventory.components", "Inventory components", None),
            ("missing_serials", "inventory_state.missing_serials", 0, "integer", "inventory.missing_serials", "Missing serials", None),
            ("serial", "inventory_state.chassis_serial", "OPENNV-SYN-0001", "string", "inventory.chassis_serial", "Chassis serial", None),
        ],
        "validation": ("inventory.missing_serials", "eq", 0, 2),
    },
    "config_state": {
        "fields": [
            ("clean", "config.clean", True, "boolean", "config.clean", "Configuration clean", "yes_no"),
            ("change", "config.last_change_id", "demo-change-0042", "string", "config.last_change_id", "Last change", None),
            ("age", "config.age_minutes", 19, "integer", "config.age_minutes", "Config age minutes", None),
        ],
        "validation": ("config.clean", "eq", True, False),
    },
    "health": {
        "fields": [
            ("score", "health.score", 97, "integer", "health.score", "Health score", None),
            ("status", "health.status", "healthy", "string", "health.status", "Health status", None),
            ("open_alerts", "health.open_alerts", 0, "integer", "health.open_alerts", "Open alerts", None),
        ],
        "validation": ("health.score", "gte", 90, 44),
    },
    "lb_virtual": {
        "fields": [
            ("virtuals", "load_balancing.virtual_servers", 12, "integer", "load_balancing.virtual_servers", "Virtual servers", None),
            ("available", "load_balancing.virtual_servers_available", 12, "integer", "load_balancing.virtual_servers_available", "Available virtual servers", None),
            ("unavailable", "load_balancing.virtual_servers_unavailable", 0, "integer", "load_balancing.virtual_servers_unavailable", "Unavailable virtual servers", None),
        ],
        "validation": ("load_balancing.virtual_servers_unavailable", "eq", 0, 3),
    },
    "lb_pool": {
        "fields": [
            ("pools", "load_balancing.pools", 8, "integer", "load_balancing.pools", "Pools/service groups", None),
            ("available", "load_balancing.pools_available", 8, "integer", "load_balancing.pools_available", "Available pools", None),
            ("unavailable", "load_balancing.pools_unavailable", 0, "integer", "load_balancing.pools_unavailable", "Unavailable pools", None),
        ],
        "validation": ("load_balancing.pools_unavailable", "eq", 0, 2),
    },
    "lb_member": {
        "fields": [
            ("members", "load_balancing.members", 32, "integer", "load_balancing.members", "Pool/service members", None),
            ("up", "load_balancing.members_up", 31, "integer", "load_balancing.members_up", "Members up", None),
            ("down", "load_balancing.members_down", 1, "integer", "load_balancing.members_down", "Members down", None),
        ],
        "validation": ("load_balancing.members_down", "lte", 1, 6),
    },
    "lb_monitor": {
        "fields": [
            ("monitors", "load_balancing.monitors", 6, "integer", "load_balancing.monitors", "Health monitors", None),
            ("enabled", "load_balancing.monitors_enabled", 6, "integer", "load_balancing.monitors_enabled", "Enabled monitors", None),
            ("failing", "load_balancing.monitors_failing", 0, "integer", "load_balancing.monitors_failing", "Failing monitors", None),
        ],
        "validation": ("load_balancing.monitors_failing", "eq", 0, 2),
    },
    "lb_server": {
        "fields": [
            ("servers", "load_balancing.servers", 20, "integer", "load_balancing.servers", "Backend servers/nodes", None),
            ("up", "load_balancing.servers_up", 20, "integer", "load_balancing.servers_up", "Servers up", None),
            ("down", "load_balancing.servers_down", 0, "integer", "load_balancing.servers_down", "Servers down", None),
        ],
        "validation": ("load_balancing.servers_down", "eq", 0, 4),
    },
    "ha_sync": {
        "fields": [
            ("state", "redundancy.state", "active", "string", "redundancy.state", "Local state", None),
            ("synced", "redundancy.config_synced", True, "boolean", "redundancy.config_synced", "Configuration synchronized", "yes_no"),
            ("ready", "redundancy.ready", True, "boolean", "redundancy.ready", "HA ready", "yes_no"),
        ],
        "validation": ("redundancy.config_synced", "eq", True, False),
    },
    "storage": {
        "fields": [
            ("filesystems", "storage.filesystems", 6, "integer", "storage.filesystems", "Filesystems", None),
            ("max_used", "storage.max_used_pct", 61.3, "number", "storage.max_used_pct", "Maximum disk used", "percent"),
            ("readonly", "storage.readonly_filesystems", 0, "integer", "storage.readonly_filesystems", "Read-only filesystems", None),
        ],
        "validation": ("storage.max_used_pct", "lte", 85, 96.4),
    },
    "system_stats": {
        "fields": [
            ("cpu", "resources.cpu_pct", 22.4, "number", "resources.cpu_pct", "CPU utilization", "percent"),
            ("memory", "resources.memory_used_pct", 48.7, "number", "resources.memory_used_pct", "Memory used", "percent"),
            ("connections", "resources.active_connections", 1842, "integer", "resources.active_connections", "Active connections", None),
        ],
        "validation": ("resources.cpu_pct", "lte", 80, 98.1),
    },
}


def c(identifier: str, command: str, category: str) -> tuple[str, str, str]:
    return identifier, command, category


PLATFORMS: dict[str, dict[str, Any]] = {
    "cisco_ios": {
        "name": "Cisco IOS",
        "aliases": ["ios", "cisco-ios"],
        "prompt": "${hostname}#${command}",
        "commands": [
            c("show_version", "show version", "system_version"),
            c("show_ip_interface_brief", "show ip interface brief", "interface_summary"),
            c("show_interfaces", "show interfaces", "interface_detail"),
            c("show_ip_route", "show ip route", "routes"),
            c("show_ip_arp", "show ip arp", "arp"),
            c("show_mac_address_table", "show mac address-table", "mac"),
            c("show_cdp_neighbors_detail", "show cdp neighbors detail", "neighbors"),
            c("show_vlan_brief", "show vlan brief", "vlans"),
            c("show_etherchannel_summary", "show etherchannel summary", "aggregation"),
            c("show_ip_ospf_neighbor", "show ip ospf neighbor", "routing_peers"),
            c("show_ip_bgp_summary", "show ip bgp summary", "routing_peers"),
            c("show_standby_brief", "show standby brief", "redundancy"),
            c("show_inventory", "show inventory", "inventory"),
            c("show_environment_all", "show environment all", "environment"),
            c("show_processes_cpu_sorted", "show processes cpu sorted", "cpu"),
            c("show_processes_memory_sorted", "show processes memory sorted", "memory"),
            c("show_logging", "show logging", "logging"),
            c("show_clock_detail", "show clock detail", "clock"),
            c("show_running_config_hostname", "show running-config | include hostname", "config_state"),
            c("show_platform", "show platform", "hardware"),
        ],
    },
    "cisco_iosxe": {
        "name": "Cisco IOS XE",
        "aliases": ["iosxe", "ios-xe", "cisco-ios-xe"],
        "prompt": "${hostname}#${command}",
        "commands": [
            c("show_version", "show version", "system_version"),
            c("show_ip_interface_brief", "show ip interface brief", "interface_summary"),
            c("show_interfaces", "show interfaces", "interface_detail"),
            c("show_ip_route", "show ip route", "routes"),
            c("show_ip_arp", "show ip arp", "arp"),
            c("show_mac_address_table", "show mac address-table", "mac"),
            c("show_lldp_neighbors_detail", "show lldp neighbors detail", "neighbors"),
            c("show_vlan_brief", "show vlan brief", "vlans"),
            c("show_etherchannel_summary", "show etherchannel summary", "aggregation"),
            c("show_ip_ospf_neighbor", "show ip ospf neighbor", "routing_peers"),
            c("show_bgp_ipv4_unicast_summary", "show bgp ipv4 unicast summary", "routing_peers"),
            c("show_redundancy", "show redundancy", "redundancy"),
            c("show_inventory", "show inventory", "inventory"),
            c("show_environment_all", "show environment all", "environment"),
            c("show_processes_cpu_platform_sorted", "show processes cpu platform sorted", "cpu"),
            c("show_platform_software_status_control_processor_brief", "show platform software status control-processor brief", "memory"),
            c("show_logging", "show logging", "logging"),
            c("show_clock_detail", "show clock detail", "clock"),
            c("show_archive_config_differences", "show archive config differences", "config_state"),
            c("show_platform", "show platform", "hardware"),
        ],
    },
    "cisco_nxos": {
        "name": "Cisco NX-OS",
        "aliases": ["nxos", "nx-os", "cisco-nxos"],
        "prompt": "${hostname}# ${command}",
        "commands": [
            c("show_version", "show version", "system_version"),
            c("show_interface_brief", "show interface brief", "interface_summary"),
            c("show_interface", "show interface", "interface_detail"),
            c("show_ip_route_vrf_all", "show ip route vrf all", "routes"),
            c("show_ip_arp_vrf_all", "show ip arp vrf all", "arp"),
            c("show_mac_address_table", "show mac address-table", "mac"),
            c("show_lldp_neighbors_detail", "show lldp neighbors detail", "neighbors"),
            c("show_vlan_brief", "show vlan brief", "vlans"),
            c("show_port_channel_summary", "show port-channel summary", "aggregation"),
            c("show_bgp_ipv4_unicast_summary", "show bgp ipv4 unicast summary", "routing_peers"),
            c("show_ip_ospf_neighbors", "show ip ospf neighbors", "routing_peers"),
            c("show_vpc_brief", "show vpc brief", "redundancy"),
            c("show_module", "show module", "hardware"),
            c("show_environment", "show environment", "environment"),
            c("show_system_resources", "show system resources", "memory"),
            c("show_processes_cpu_sort", "show processes cpu sort", "cpu"),
            c("show_logging_last_50", "show logging last 50", "logging"),
            c("show_clock", "show clock", "clock"),
            c("show_inventory", "show inventory", "inventory"),
            c("show_checkpoint_summary", "show checkpoint summary", "config_state"),
        ],
    },
    "cisco_iosxr": {
        "name": "Cisco IOS XR",
        "aliases": ["iosxr", "ios-xr", "cisco-ios-xr"],
        "prompt": "RP/0/RP0/CPU0:${hostname}#${command}",
        "commands": [
            c("show_version", "show version", "system_version"),
            c("show_ipv4_interface_brief", "show ipv4 interface brief", "interface_summary"),
            c("show_interfaces", "show interfaces", "interface_detail"),
            c("show_route_ipv4_unicast", "show route ipv4 unicast", "routes"),
            c("show_arp", "show arp", "arp"),
            c("show_l2vpn_forwarding_bridge_domain_mac_address", "show l2vpn forwarding bridge-domain mac-address", "mac"),
            c("show_lldp_neighbors_detail", "show lldp neighbors detail", "neighbors"),
            c("show_l2vpn_bridge_domain_brief", "show l2vpn bridge-domain brief", "vlans"),
            c("show_bundle_brief", "show bundle brief", "aggregation"),
            c("show_bgp_ipv4_unicast_summary", "show bgp ipv4 unicast summary", "routing_peers"),
            c("show_ospf_neighbor", "show ospf neighbor", "routing_peers"),
            c("show_redundancy_summary", "show redundancy summary", "redundancy"),
            c("show_platform", "show platform", "hardware"),
            c("show_environment_all", "show environment all", "environment"),
            c("show_processes_cpu", "show processes cpu", "cpu"),
            c("show_memory_summary", "show memory summary", "memory"),
            c("show_logging_last_50", "show logging last 50", "logging"),
            c("show_clock", "show clock", "clock"),
            c("show_inventory", "show inventory", "inventory"),
            c("show_configuration_commit_list", "show configuration commit list", "config_state"),
        ],
    },
    "arista_eos": {
        "name": "Arista EOS",
        "aliases": ["eos", "arista-eos"],
        "prompt": "${hostname}#${command}",
        "commands": [
            c("show_version", "show version", "system_version"),
            c("show_ip_interface_brief", "show ip interface brief", "interface_summary"),
            c("show_interfaces", "show interfaces", "interface_detail"),
            c("show_ip_route", "show ip route", "routes"),
            c("show_ip_arp", "show ip arp", "arp"),
            c("show_mac_address_table", "show mac address-table", "mac"),
            c("show_lldp_neighbors_detail", "show lldp neighbors detail", "neighbors"),
            c("show_vlan", "show vlan", "vlans"),
            c("show_port_channel_summary", "show port-channel summary", "aggregation"),
            c("show_ip_bgp_summary", "show ip bgp summary", "routing_peers"),
            c("show_ip_ospf_neighbor", "show ip ospf neighbor", "routing_peers"),
            c("show_mlag", "show mlag", "redundancy"),
            c("show_inventory", "show inventory", "inventory"),
            c("show_environment_all", "show environment all", "environment"),
            c("show_processes_top_once", "show processes top once", "cpu"),
            c("show_system_resources", "show system resources", "memory"),
            c("show_logging_last_50", "show logging last 50", "logging"),
            c("show_clock", "show clock", "clock"),
            c("show_running_config_hostname", "show running-config | include hostname", "config_state"),
            c("show_platform", "show platform", "hardware"),
        ],
    },
    "juniper_junos": {
        "name": "Juniper Junos",
        "aliases": ["junos", "juniper-junos"],
        "prompt": "${hostname}> ${command}",
        "commands": [
            c("show_version", "show version", "system_version"),
            c("show_interfaces_terse", "show interfaces terse", "interface_summary"),
            c("show_interfaces_extensive", "show interfaces extensive", "interface_detail"),
            c("show_route_summary", "show route summary", "routes"),
            c("show_arp_no_resolve", "show arp no-resolve", "arp"),
            c("show_ethernet_switching_table", "show ethernet-switching table", "mac"),
            c("show_lldp_neighbors_detail", "show lldp neighbors detail", "neighbors"),
            c("show_vlans", "show vlans", "vlans"),
            c("show_lacp_interfaces", "show lacp interfaces", "aggregation"),
            c("show_bgp_summary", "show bgp summary", "routing_peers"),
            c("show_ospf_neighbor", "show ospf neighbor", "routing_peers"),
            c("show_chassis_routing_engine", "show chassis routing-engine", "redundancy"),
            c("show_chassis_hardware", "show chassis hardware", "hardware"),
            c("show_chassis_environment", "show chassis environment", "environment"),
            c("show_system_processes_extensive", "show system processes extensive", "cpu"),
            c("show_system_memory", "show system memory", "memory"),
            c("show_log_messages_last_50", "show log messages | last 50", "logging"),
            c("show_system_uptime", "show system uptime", "clock"),
            c("show_system_commit", "show system commit", "config_state"),
            c("show_chassis_alarms", "show chassis alarms", "health"),
        ],
    },
    "f5_tmos": {
        "name": "F5 BIG-IP TMOS",
        "aliases": ["f5", "bigip", "big-ip", "tmos"],
        "prompt": "${hostname}(active)(/Common)(tmos)# ${command}",
        "commands": [
            c("show_sys_version", "show sys version", "system_version"),
            c("show_net_interface", "show net interface", "interface_summary"),
            c("show_net_interface_all_properties", "show net interface all-properties", "interface_detail"),
            c("show_net_route", "show net route", "routes"),
            c("show_net_arp", "show net arp", "arp"),
            c("show_ltm_node", "show ltm node", "lb_server"),
            c("show_net_vlan", "show net vlan", "vlans"),
            c("show_ltm_pool_members", "show ltm pool members", "lb_member"),
            c("show_ltm_virtual", "show ltm virtual", "lb_virtual"),
            c("show_ltm_pool", "show ltm pool", "lb_pool"),
            c("show_ltm_monitor", "show ltm monitor", "lb_monitor"),
            c("show_sys_failover", "show sys failover", "redundancy"),
            c("show_sys_hardware", "show sys hardware", "hardware"),
            c("show_sys_disk", "show sys disk", "storage"),
            c("show_sys_cpu", "show sys cpu", "cpu"),
            c("show_sys_memory", "show sys memory", "memory"),
            c("show_sys_log_ltm", "show sys log ltm", "logging"),
            c("show_sys_clock", "show sys clock", "clock"),
            c("show_cm_device", "show cm device", "inventory"),
            c("show_cm_sync_status", "show cm sync-status", "ha_sync"),
        ],
    },
    "citrix_adc": {
        "name": "Citrix ADC / NetScaler",
        "aliases": ["citrix", "netscaler", "citrix-adc"],
        "prompt": "> ${command}",
        "commands": [
            c("show_ns_version", "show ns version", "system_version"),
            c("show_interface", "show interface", "interface_summary"),
            c("show_interface_detail", "show interface -detail", "interface_detail"),
            c("show_route", "show route", "routes"),
            c("show_arp", "show arp", "arp"),
            c("show_ns_ip", "show ns ip", "neighbors"),
            c("show_vlan", "show vlan", "vlans"),
            c("show_servicegroup", "show serviceGroup", "lb_pool"),
            c("show_lb_vserver", "show lb vserver", "lb_virtual"),
            c("show_service", "show service", "lb_member"),
            c("show_lb_monitor", "show lb monitor", "lb_monitor"),
            c("show_ha_node", "show ha node", "redundancy"),
            c("show_hardware", "show hardware", "hardware"),
            c("show_cluster_instance", "show cluster instance", "redundancy"),
            c("stat_system", "stat system", "system_stats"),
            c("stat_lb_vserver", "stat lb vserver", "lb_virtual"),
            c("show_audit_messages", "show audit messages", "logging"),
            c("show_ns_mode", "show ns mode", "config_state"),
            c("show_server", "show server", "lb_server"),
            c("show_ns_runningconfig", "show ns runningConfig", "config_state"),
        ],
    },
}


PLATFORM_SYSTEM_FIXTURES: dict[str, tuple[str, str]] = {
    "cisco_ios": ("15.9(3)M-open", "flash:open-ios-image.bin"),
    "cisco_iosxe": ("17.12.4-open", "bootflash:open-iosxe-image.bin"),
    "cisco_nxos": ("10.4(3)-open", "bootflash:/open-nxos-image.bin"),
    "cisco_iosxr": ("24.2.1-open", "open-iosxr-package.x86_64"),
    "arista_eos": ("4.32.1F-open", "flash:/open-eos-image.swi"),
    "juniper_junos": ("24.2R1-open", "open-junos-install.tgz"),
    "f5_tmos": ("17.1.1-open", "open-bigip-volume"),
    "citrix_adc": ("14.1-open", "open-citrixadc-build.tgz"),
}


def set_path(document: dict[str, Any], path: str, value: Any) -> None:
    current = document
    tokens = path.split(".")
    for token in tokens[:-1]:
        current = current.setdefault(token, {})
    current[tokens[-1]] = value


def variable_rule(source: str, generator: str | None) -> dict[str, Any]:
    full_source = f"inventory.{source}"
    if generator:
        rule: dict[str, Any] = {"generator": {"name": generator, "source": full_source}}
        if generator == "percent":
            rule["generator"]["precision"] = 1
        return rule
    return {"source": full_source}


DEGRADED_OVERRIDES: dict[str, dict[str, Any]] = {
    "system_version": {"system.oper_state": "down"},
    "interface_summary": {"interfaces.up": 42, "interfaces.down": 6},
    "interface_detail": {"interfaces.error_count": 14, "interfaces.utilization_pct": 97.8},
    "routes": {"routes.total": 118, "routes.default_present": False, "routes.stale": 9},
    "arp": {"arp.entries": 96, "arp.incomplete": 5},
    "mac": {"mac.entries": 0, "mac.dynamic": 0},
    "neighbors": {"neighbors.count": 4, "neighbors.expected_matches": False},
    "vlans": {"vlans.active": 0},
    "aggregation": {"aggregation.up": 2, "aggregation.down": 2},
    "routing_peers": {
        "routing.peers_established": 5,
        "routing.established_ratio_pct": 62.5,
    },
    "redundancy": {
        "redundancy.peer_state": "standby-cold",
        "redundancy.ready": False,
    },
    "hardware": {"hardware.modules_ok": 2, "hardware.faulty_modules": 1},
    "environment": {
        "environment.temp_c": 93.0,
        "environment.fans_ok": False,
        "environment.psus_ok": False,
    },
    "cpu": {"resources.cpu_pct": 98.1, "resources.load_5m": 17.9},
    "memory": {"resources.memory_used_pct": 97.0, "resources.memory_free_mb": 128},
    "logging": {
        "logging.critical_count": 4,
        "logging.warning_count": 18,
        "logging.last_event": "synthetic link and power alarm",
    },
    "clock": {"clock.synced": False, "clock.offset_ms": 1802.0},
    "inventory": {"inventory_state.missing_serials": 2},
    "config_state": {
        "config.clean": False,
        "config.last_change_id": "demo-change-pending",
        "config.age_minutes": 2,
    },
    "health": {"health.score": 44, "health.status": "critical", "health.open_alerts": 7},
    "lb_virtual": {
        "load_balancing.virtual_servers_available": 9,
        "load_balancing.virtual_servers_unavailable": 3,
    },
    "lb_pool": {
        "load_balancing.pools_available": 6,
        "load_balancing.pools_unavailable": 2,
    },
    "lb_member": {"load_balancing.members_up": 26, "load_balancing.members_down": 6},
    "lb_monitor": {
        "load_balancing.monitors_enabled": 6,
        "load_balancing.monitors_failing": 2,
    },
    "lb_server": {"load_balancing.servers_up": 16, "load_balancing.servers_down": 4},
    "ha_sync": {"redundancy.config_synced": False, "redundancy.ready": False},
    "storage": {"storage.max_used_pct": 96.4, "storage.readonly_filesystems": 1},
    "system_stats": {
        "resources.cpu_pct": 98.1,
        "resources.memory_used_pct": 94.0,
        "resources.active_connections": 24576,
    },
}


def get_path(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for token in path.split("."):
        current = current[token]
    return current


def degraded_inventory(category_name: str, healthy: dict[str, Any]) -> dict[str, Any]:
    inventory = deepcopy(healthy)
    for path, value in DEGRADED_OVERRIDES[category_name].items():
        set_path(inventory, path, value)
    return inventory


def state_word(value: bool, healthy: str = "up", unhealthy: str = "down") -> str:
    return healthy if value else unhealthy


def record_lines(
    platform: str,
    identifier: str,
    command: str,
    category_name: str,
    inventory: dict[str, Any],
) -> list[str]:
    """Build deterministic representative records without executable templates.

    The records intentionally resemble each vendor's hierarchy and table shape,
    but remain original synthetic data. Summary metrics stay separate and are
    always rendered from their normalized inventory fields.
    """

    degraded = any(
        get_path(inventory, path) == value
        for path, value in DEGRADED_OVERRIDES[category_name].items()
    )
    bad = "down" if degraded else "up"
    unavailable = "unavailable" if degraded else "available"
    disabled = "disabled" if degraded else "enabled"

    if category_name == "system_version":
        if platform in {"cisco_ios", "cisco_iosxe"}:
            return [
                "Cisco Synthetic Network OS Software, RELEASE SOFTWARE",
                "Technical Support: https://example.invalid/opennv",
                "Compiled Fri 16-Aug-26 00:00 by opennv-build",
                "ROM: Bootstrap program is OPENNV",
                "Configuration register is 0x2102",
            ]
        if platform == "cisco_nxos":
            return [
                "  BIOS: version 08.00",
                "  kickstart: version synthetic",
                "Hardware",
                "  cisco Nexus9000 synthetic chassis with 16384000 kB of memory",
                "  Device name: open-nv-nxos-01",
            ]
        if platform == "cisco_iosxr":
            return [
                "Cisco IOS XR Software, Version synthetic",
                "Copyright (c) OpenNV synthetic fixture authors",
                "Build Information:",
                " Built By     : opennv-build",
                " Build Host   : fixture-builder",
            ]
        if platform == "arista_eos":
            return [
                "Arista synthetic DCS-7280 platform",
                "Hardware version: 01.00",
                "Serial number: OPENNV-EOS-0001",
                "System MAC address: 02:00:00:00:00:51",
                "Total memory: 8096000 kB",
            ]
        if platform == "juniper_junos":
            return [
                "Model: mx204-synthetic",
                "Junos: synthetic",
                "JUNOS OS Kernel 64-bit [synthetic]",
                "JUNOS network stack and utilities [synthetic]",
                "JUNOS routing software suite [synthetic]",
            ]
        if platform == "f5_tmos":
            return [
                "Sys::Version",
                "Main Package",
                "  Product     BIG-IP",
                "  Build       0.0.1",
                "  Edition     OpenNV Synthetic",
            ]
        return [
            "NetScaler NS synthetic build",
            "Done",
            "Kernel: synthetic 64-bit",
            "Platform: Citrix ADC virtual appliance",
            "Serial Number: OPENNV-ADC-0001",
        ]

    if category_name == "interface_summary":
        if platform == "juniper_junos":
            return [
                "ge-0/0/0                up    up",
                f"ge-0/0/1                up    {bad}",
                "lo0                     up    up",
                "lo0.0                   up    up   inet     192.0.2.11/32",
            ]
        if platform == "f5_tmos":
            return [
                "1.1        up      up        10000  full    none",
                f"1.2        up      {bad:<10}10000  full    none",
                "mgmt       up      up         1000  full    none",
                "2.1        up      up        25000  full    none",
            ]
        if platform == "citrix_adc":
            return [
                "1/1  UP    UP      10000  FULL  02:00:00:00:10:01",
                f"1/2  UP    {bad.upper():<8}10000  FULL  02:00:00:00:10:02",
                "0/1  UP    UP       1000  FULL  02:00:00:00:10:ff",
                "LA/1 UP    UP      20000  FULL  02:00:00:00:10:10",
            ]
        if platform == "cisco_nxos":
            return [
                "Eth1/1       uplink-a         eth   10G     1500  up",
                f"Eth1/2       uplink-b         eth   10G     1500  {bad}",
                "mgmt0        management       eth   1G      1500  up",
                "Vlan100      server-gateway   vlan  --      1500  up",
            ]
        if platform == "cisco_iosxr":
            return [
                "Gi0/0/0/0          192.0.2.1       Up              Up       default",
                f"Gi0/0/0/1          198.51.100.1    Up              {bad.title():<9}default",
                "Lo0                 203.0.113.11    Up              Up       default",
                "BE10                10.0.0.1        Up              Up       default",
            ]
        if platform == "arista_eos":
            return [
                "Ethernet1              192.0.2.1/31       up           up",
                f"Ethernet2              198.51.100.1/31    up           {bad}",
                "Loopback0               203.0.113.11/32    up           up",
                "Vlan100                 10.0.0.1/24        up           up",
            ]
        return [
            "GigabitEthernet1/0/1   192.0.2.1       YES manual up                    up",
            f"GigabitEthernet1/0/2   198.51.100.1    YES manual up                    {bad}",
            "Loopback0              203.0.113.11    YES manual up                    up",
            "Vlan100                10.0.0.1        YES manual up                    up",
        ]

    if category_name == "interface_detail":
        if platform == "juniper_junos":
            return [
                "Physical interface: ge-0/0/0, Enabled, Physical link is Up",
                "  Link-level type: Ethernet, Speed: 10Gbps, BPDU Error: None",
                "  Input rate     : 312000000 bps (39000 pps)",
                "  Output rate    : 184000000 bps (23000 pps)",
                f"  Carrier transitions: {14 if degraded else 0}",
                "  Logical interface ge-0/0/0.0 (Index 333) (SNMP ifIndex 533)",
            ]
        if platform == "f5_tmos":
            return [
                "Net::Interface",
                "Name  Status  Bits In  Bits Out  Drops  Errors  Media",
                f"1.1   {bad:<7}312.0M   184.0M    0      {14 if degraded else 0:<7}10000T-FD",
                "  Mac Address  02:00:00:00:20:01",
                "  Flow Control tx-rx",
                "  Lldp Admin   txonly",
            ]
        if platform == "citrix_adc":
            return [
                "1) Interface 1/1",
                f"   state: {bad.upper()}, link state: {bad.upper()}, speed: 10000, duplex: FULL",
                "   MAC: 02:00:00:00:30:01, flow control: OFF",
                "   RX packets: 1242100, TX packets: 1198830",
                f"   RX errors: {14 if degraded else 0}, TX errors: 0",
                "Done",
            ]
        name = "Ethernet1/1" if platform == "cisco_nxos" else "GigabitEthernet0/0/0/0" if platform == "cisco_iosxr" else "Ethernet1"
        return [
            f"{name} is {bad}, line protocol is {bad}",
            "  Hardware is Ethernet, address is 0200.0000.4001 (bia 0200.0000.4001)",
            "  Full-duplex, 10Gb/s, media type is synthetic fiber",
            "  5 minute input rate 312000000 bits/sec, 39000 packets/sec",
            "  5 minute output rate 184000000 bits/sec, 23000 packets/sec",
            f"  {14 if degraded else 0} input errors, 0 CRC, 0 frame, 0 overrun, 0 ignored",
        ]

    if category_name == "routes":
        if platform == "juniper_junos":
            return [
                "Autonomous system number: 65000",
                "Router ID: 203.0.113.11",
                "Highwater Mark (All time): 256 routes",
                "inet.0: 128 destinations, 256 routes (127 active, 0 holddown, 1 hidden)",
                "inet6.0: 32 destinations, 64 routes (32 active, 0 holddown, 0 hidden)",
            ]
        if platform == "f5_tmos":
            return [
                "Net::Routes",
                "Name              Destination        Type       Gateway",
                ("default           default            missing    -" if degraded else "default           default            gw         192.0.2.254"),
                "server-net        10.0.0.0/24        interface  /Common/server-vlan",
                "monitor-net       198.51.100.0/24    gw         192.0.2.253",
            ]
        if platform == "citrix_adc":
            return [
                "Network          Netmask          Gateway        Type   State",
                ("0.0.0.0          0.0.0.0          -              STATIC MISSING" if degraded else "0.0.0.0          0.0.0.0          192.0.2.254    STATIC UP"),
                "10.0.0.0         255.255.255.0    10.0.0.1       DIRECT UP",
                f"198.51.100.0     255.255.255.0    192.0.2.253    STATIC {bad.upper()}",
                "Done",
            ]
        if platform == "cisco_iosxr":
            return [
                "Codes: C - connected, S - static, O - OSPF, B - BGP, L - local",
                ("% No gateway of last resort configured" if degraded else "S*   0.0.0.0/0 [1/0] via 192.0.2.254, 2d03h"),
                "L    10.0.0.1/32 is directly connected, 4w2d, Bundle-Ether10",
                "C    10.0.0.0/24 is directly connected, 4w2d, Bundle-Ether10",
                f"O    198.51.100.0/24 [110/20] via 192.0.2.2, 00:04:12, {('unresolved' if degraded else 'GigabitEthernet0/0/0/0')}",
            ]
        return [
            "Codes: C - connected, S - static, O - OSPF, B - BGP",
            ("Gateway of last resort is not set" if degraded else "Gateway of last resort is 192.0.2.254 to network 0.0.0.0"),
            ("% No candidate default route is installed" if degraded else "S*    0.0.0.0/0 [1/0] via 192.0.2.254"),
            "C     10.0.0.0/24 is directly connected, Vlan100",
            f"O     198.51.100.0/24 [110/20] via 192.0.2.2, 00:04:12, {bad if degraded else 'Ethernet1'}",
        ]

    if category_name == "arp":
        if platform == "juniper_junos":
            return [
                "MAC Address       Address         Name                      Interface           Flags",
                "02:00:00:00:50:01 192.0.2.2       192.0.2.2                 ge-0/0/0.0          none",
                "02:00:00:00:50:02 10.0.0.20       10.0.0.20                 irb.100             none",
                f"{('(incomplete)' if degraded else '02:00:00:00:50:03'):<17}198.51.100.2    198.51.100.2             ge-0/0/1.0          none",
            ]
        if platform == "f5_tmos":
            return [
                "Net::Arp",
                "Ip Address      Mac Address         Vlan                 Expire-in-sec",
                "192.0.2.2       02:00:00:00:50:01  /Common/external     178",
                "10.0.0.20       02:00:00:00:50:02  /Common/server       212",
                f"198.51.100.2    {('(incomplete)' if degraded else '02:00:00:00:50:03'):<18}/Common/monitor      4",
            ]
        if platform == "citrix_adc":
            return [
                "1) IP: 192.0.2.2, MAC: 02:00:00:00:50:01, VLAN: 100, Interface: 1/1",
                "2) IP: 10.0.0.20, MAC: 02:00:00:00:50:02, VLAN: 200, Interface: 1/2",
                f"3) IP: 198.51.100.2, MAC: {('(incomplete)' if degraded else '02:00:00:00:50:03')}, VLAN: 300, Interface: 1/3",
                "Flags: DYNAMIC",
                "Done",
            ]
        return [
            "Protocol  Address          Age (min)  Hardware Addr   Type   Interface",
            "Internet  192.0.2.2              2   0200.0000.5001  ARPA   Ethernet1",
            "Internet  10.0.0.20              7   0200.0000.5002  ARPA   Vlan100",
            f"Internet  198.51.100.2           0   {('Incomplete' if degraded else '0200.0000.5003'):<14}ARPA   Ethernet2",
        ]

    if category_name == "mac":
        if platform == "juniper_junos":
            if degraded:
                return [
                    "MAC flags (S - static, D - dynamic, L - locally learned)",
                    "Ethernet switching table : 0 entries, 0 learned",
                    "VLAN              MAC address       Type         Age Interfaces",
                    "No ethernet-switching entries found",
                ]
            return [
                "MAC flags (S - static, D - dynamic, L - locally learned)",
                "Ethernet switching table : 742 entries, 742 learned",
                "VLAN              MAC address       Type         Age Interfaces",
                "server-vlan       02:00:00:00:60:01 Learn          0 ge-0/0/2.0",
                "server-vlan       02:00:00:00:60:02 Learn          0 ae1.0",
            ]
        if platform == "cisco_iosxr":
            if degraded:
                return [
                    "To Resynchronize MAC table from the Network, use the command:",
                    "l2vpn resynchronize forwarding mac-address-table location all",
                    "Mac Address     Type    Learned from/Filtered on     LC learned Resync Age",
                    "No MAC addresses found in the selected bridge domains",
                ]
            return [
                "To Resynchronize MAC table from the Network, use the command:",
                "l2vpn resynchronize forwarding mac-address-table location all",
                "Mac Address     Type    Learned from/Filtered on     LC learned Resync Age",
                "0200.0000.6001  dynamic Bundle-Ether10.100           0/0/CPU0   N/A    00:02:11",
                f"0200.0000.6002  {('drop' if degraded else 'dynamic'):<7}GigabitEthernet0/0/0/1.100 0/0/CPU0   N/A    00:01:22",
                "Bridge-domain: server-bd, 2 MAC addresses",
            ]
        if degraded:
            return [
                "          Mac Address Table",
                "-------------------------------------------",
                "Vlan    Mac Address       Type        Ports",
                "No dynamic or static MAC addresses present",
            ]
        return [
            "          Mac Address Table",
            "-------------------------------------------",
            "Vlan    Mac Address       Type        Ports",
            " 100    0200.0000.6001    DYNAMIC     Ethernet1",
            " 100    0200.0000.6002    DYNAMIC     Port-channel10",
            f" 200    0200.0000.6003    {('DROP' if degraded else 'DYNAMIC'):<12}Ethernet2",
        ]

    if category_name == "neighbors":
        if platform == "citrix_adc" and identifier == "show_ns_ip":
            return [
                "1) IP: 192.0.2.10, Netmask: 255.255.255.0, Type: NSIP",
                "   State: Enabled, ARP: Enabled, ICMP: Enabled, Management Access: Enabled",
                "2) IP: 10.0.0.10, Netmask: 255.255.255.0, Type: SNIP",
                f"   State: {('Disabled' if degraded else 'Enabled')}, ARP: Enabled, ICMP: Enabled, Management Access: Disabled",
                "3) IP: 198.51.100.10, Netmask: 255.255.255.0, Type: SNIP",
                "   State: Enabled, Dynamic Routing: Enabled",
                "Done",
            ]
        if platform == "juniper_junos":
            return [
                "Local interface    Parent interface    Chassis Id          Port info          System Name",
                "ge-0/0/0           -                   02:00:00:00:70:01 Ethernet49         leaf-02",
                f"ge-0/0/1           -                   02:00:00:00:70:02 Ethernet1          {('unknown' if degraded else 'border-01')}",
                "Neighbor detail:",
                "  Management address: 192.0.2.22, System capabilities: Bridge Router",
                "  Port description: synthetic fabric uplink",
            ]
        protocol = "CDP" if "cdp" in identifier else "LLDP"
        return [
            f"{protocol} neighbor detail for synthetic topology",
            "------------------------------------------------",
            "Device ID: leaf-02.example.invalid",
            "  Local Interface: Ethernet1, Port ID: Ethernet49",
            "  Management Address: 192.0.2.22, Capability: Bridge Router",
            "Device ID: border-01.example.invalid",
            f"  Local Interface: Ethernet2, Port ID: Ethernet1, State: {bad}",
        ]

    if category_name == "vlans":
        if platform == "juniper_junos":
            return [
                "Routing instance        VLAN name             Tag          Interfaces",
                f"default-switch          server-vlan           100          {('none' if degraded else 'ge-0/0/2.0*')}",
                f"default-switch          storage-vlan          200          {('none' if degraded else 'ae1.0*')}",
                f"default-switch          monitor-vlan          300          {('none' if degraded else 'ge-0/0/3.0*')}",
            ]
        if platform == "f5_tmos":
            return [
                "Net::Vlan",
                "Name             Tag    Interfaces",
                f"/Common/external  100    {('none' if degraded else '1.1, trunk-uplink')}",
                f"/Common/server    200    {('none' if degraded else '1.2, trunk-server')}",
                f"/Common/monitor   300    {('none' if degraded else '1.3')}",
            ]
        if platform == "citrix_adc":
            return [
                "1) VLAN ID: 100, Alias Name: external",
                f"   Interfaces: {('none' if degraded else '1/1, LA/1')}; IPs: 192.0.2.10",
                "2) VLAN ID: 200, Alias Name: server",
                f"   Interfaces: {('none' if degraded else '1/2, LA/2')}; IPs: 10.0.0.10",
                "Done",
            ]
        return [
            "VLAN Name                             Status    Ports",
            "---- -------------------------------- --------- -------------------------------",
            f"100  server-vlan                      {('suspended' if degraded else 'active'):<9}{('none' if degraded else 'Eth1, Eth2, Po10')}",
            f"200  storage-vlan                     {('suspended' if degraded else 'active'):<9}{('none' if degraded else 'Eth3, Eth4, Po20')}",
            f"300  monitor-vlan                     {('suspended' if degraded else 'active'):<9}Eth5",
        ]

    if category_name == "aggregation":
        if platform == "juniper_junos":
            return [
                "Aggregated interface: ae1",
                "  LACP state: Role Exp Def Dist Col Syn Aggr Timeout Activity",
                "  ge-0/0/2 Actor   No  No  Yes Yes Yes Yes Yes Fast Active",
                f"  ge-0/0/3 Actor   No  {('Yes' if degraded else 'No ')} No  No  No  No  Yes Fast Active",
                "  Mux state: Collecting distributing",
            ]
        if platform == "cisco_iosxr":
            return [
                "Name        Status      Links  Active  Standby  Configured BW (kbps)",
                "Bundle-Ether10 Up           2       2        0             20000000",
                f"Bundle-Ether20 {('Down' if degraded else 'Up'):<12}2       {('0' if degraded else '2')}        0             20000000",
                "  Gi0/0/0/2   Active, distributing",
                f"  Gi0/0/0/3   {('Inactive, link down' if degraded else 'Active, distributing')}",
            ]
        if platform == "arista_eos":
            return [
                "Flags: D - Down, P - bundled in port-channel, I - individual",
                "Group Port-Channel  Type     Protocol Member Ports",
                "10    Po10(SU)      Eth      LACP     Et1(P) Et2(P)",
                f"20    Po20({('SD' if degraded else 'SU')})      Eth      LACP     Et3(P) Et4({('D' if degraded else 'P')})",
                "Minimum links: 1, fallback: disabled",
            ]
        return [
            "Group  Port-channel  Protocol    Ports",
            "------+-------------+-----------+-----------------------------------------------",
            "10     Po10(SU)         LACP      Eth1(P) Eth2(P)",
            f"20     Po20({('SD' if degraded else 'SU')})         LACP      Eth3(P) Eth4({('D' if degraded else 'P')})",
            "Flags: D - down, P - bundled, S - layer2, U - in use",
        ]

    if category_name == "routing_peers":
        if "bgp" in identifier:
            if platform == "juniper_junos":
                return [
                    "Groups: 2 Peers: 8 Down peers: 0",
                    "Table          Tot Paths  Act Paths Suppressed History Damp State Pending",
                    "inet.0               256        128          0       0    0          0",
                    "Peer               AS      InPkt     OutPkt    OutQ   Flaps Last Up/Dwn State|#Active/Received/Accepted/Damped...",
                    "192.0.2.2       64512      88421      87112       0       0 2d 03:11:04 128/128/128/0",
                    f"198.51.100.2    64513      12004      11998       0       3 00:04:12 {('Active' if degraded else '64/64/64/0')}",
                ]
            return [
                "BGP router identifier 203.0.113.11, local AS number 65000",
                "BGP table version is 417, main routing table version 417",
                "Neighbor        V    AS MsgRcvd MsgSent TblVer InQ OutQ Up/Down  State/PfxRcd",
                "192.0.2.2       4 64512   88421   87112    417   0    0 2d03h            128",
                f"198.51.100.2    4 64513   12004   11998    417   0    0 00:04:12 {('Active' if degraded else '64')}",
            ]
        if platform == "juniper_junos":
            return [
                "Address          Interface              State     ID               Pri  Dead",
                "192.0.2.2        ge-0/0/0.0             Full      203.0.113.2        128    33",
                f"198.51.100.2     ge-0/0/1.0             {('ExStart' if degraded else 'Full'):<9}203.0.113.3        128    31",
                "10.0.0.2         irb.100                Full      203.0.113.4        128    36",
                "OSPF instance master, area 0.0.0.0",
            ]
        return [
            "Neighbor ID     Pri   State           Dead Time   Address         Interface",
            "203.0.113.2       1   FULL/DR         00:00:33    192.0.2.2       Ethernet1",
            f"203.0.113.3       1   {('EXSTART/DR' if degraded else 'FULL/BDR'):<16}00:00:31    198.51.100.2    Ethernet2",
            "203.0.113.4       1   FULL/DROTHER    00:00:36    10.0.0.2        Vlan100",
            "Process 1, area 0.0.0.0, hello 10, dead 40",
        ]

    if category_name in {"redundancy", "ha_sync"}:
        if platform == "f5_tmos":
            if identifier == "show_cm_sync_status":
                return [
                    "Cm::Device Group: /Common/sync-failover-group",
                    f"Color    {('red' if degraded else 'green')}",
                    f"Status   {('Not All Devices Synced' if degraded else 'In Sync')}",
                    f"Summary  {('Changes pending on peer device' if degraded else 'All devices in the device group are in sync')}",
                    "Connected device: /Common/demo-f5-tmos-02",
                    f"Recommended action: {('Review device trust and sync changes' if degraded else 'None')}",
                ]
            return [
                "Sys::Failover",
                "Unit ID  1",
                f"Failover State  {('offline' if degraded else 'active')}",
                "Peer Address  192.0.2.12",
                f"Color  {('red' if degraded else 'green')}",
            ]
        if platform == "citrix_adc":
            if identifier == "show_cluster_instance":
                return [
                    "1) Cluster Instance ID: 1",
                    f"   Operational State: {('DOWN' if degraded else 'UP')}, Admin State: ENABLED",
                    "   Configuration Coordinator: Node 0, Process Health: 100%",
                    "   Node 0: 192.0.2.10, State: ACTIVE, Health: UP",
                    f"   Node 1: 192.0.2.11, State: {('INACTIVE' if degraded else 'ACTIVE')}, Health: {('DOWN' if degraded else 'UP')}",
                    "Done",
                ]
            return [
                "1) Node ID: 0",
                "   IP: 192.0.2.10, State: Primary, Master State: Primary",
                f"   Sync State: {('DISABLED' if degraded else 'ENABLED')}, Propagation: {('FAILED' if degraded else 'SUCCESS')}",
                "2) Node ID: 1",
                f"   IP: 192.0.2.11, State: {('DOWN' if degraded else 'Secondary')}",
            ]
        if platform == "cisco_nxos":
            return [
                "vPC domain id                     : 10",
                f"Peer status                       : {('peer link is down' if degraded else 'peer adjacency formed ok')}",
                f"vPC keep-alive status             : {('peer is not alive' if degraded else 'peer is alive')}",
                "Configuration consistency status  : success",
                f"Per-vlan consistency status       : {('failed' if degraded else 'success')}",
                "vPC role                           : primary",
                f"Number of vPCs configured          : 4 ({'2 down' if degraded else 'all up'})",
            ]
        if platform == "arista_eos":
            return [
                "MLAG Configuration:",
                "domain-id                          : MLAG-DFW01",
                "local-interface                    : Vlan4094",
                "peer-address                       : 192.0.2.22",
                "peer-link                          : Port-Channel1000",
                "MLAG Status:",
                f"state                              : {('Inactive' if degraded else 'Active')}",
                f"peer-link status                   : {('Down' if degraded else 'Up')}",
            ]
        if platform == "juniper_junos":
            return [
                "Routing Engine status:",
                "  Slot 0:",
                "    Current state                  Master",
                "    Election priority              Master (default)",
                "  Slot 1:",
                f"    Current state                  {('Present' if degraded else 'Backup')}",
                f"    Redundancy state               {('Not ready' if degraded else 'Ready')}",
            ]
        if platform == "cisco_iosxr":
            return [
                "Redundancy information for node 0/RP0/CPU0:",
                "============================================",
                "Node 0/RP0/CPU0 is in ACTIVE role",
                "Node 0/RP1/CPU0 is in STANDBY role",
                f"Standby node in {('COLD' if degraded else 'READY')} state",
                f"NSR state: {('not ready' if degraded else 'ready')}",
            ]
        if platform == "cisco_iosxe":
            return [
                "Redundant System Information :",
                "------------------------------",
                "Available system uptime = 4 weeks, 2 days, 1 hour",
                "Switchovers system experienced = 0",
                "Current Processor Information : Active",
                f"Peer Processor Information    : {('Standby cold' if degraded else 'Standby hot')}",
            ]
        if platform == "cisco_ios":
            return [
                "                     P indicates configured to preempt.",
                "                     |",
                "Interface   Grp  Pri P State   Active          Standby         Virtual IP",
                "Vl100       10   110 P Active  local           10.0.0.2        10.0.0.1",
                f"Vl200       20   100 P {('Listen' if degraded else 'Standby'):<7}10.0.1.2        {('unknown' if degraded else 'local'):<16}10.0.1.1",
            ]
        return [
            "Redundant System Information",
            "----------------------------",
            "Available system uptime = 4 weeks, 2 days, 1 hour",
            "Current processor information:",
            "  Active location = slot 1",
            f"  Peer communication = {('lost' if degraded else 'operational')}",
        ]

    if category_name in {"hardware", "inventory"}:
        if platform == "f5_tmos" and identifier == "show_cm_device":
            return [
                "Cm::Device: /Common/demo-f5-tmos-01",
                "Hostname                     demo-f5-tmos-01.example.invalid",
                "Management IP                192.0.2.10",
                "ConfigSync IP                192.0.2.10",
                "Mirror IP                    10.0.0.10",
                "Failover State               active",
                f"Device Trust                 {('disconnected' if degraded else 'connected')}",
            ]
        if platform == "f5_tmos":
            return [
                "Sys::Hardware",
                "Chassis Information",
                "  Type                         BIG-IP Virtual Edition synthetic",
                "  Serial Number                OPENNV-SYN-0001",
                "System Information",
                "  Type                         x86_64 synthetic appliance",
                f"  Hardware Status              {('faulty' if degraded else 'ok')}",
            ]
        if platform == "juniper_junos":
            return [
                "Hardware inventory:",
                "Item             Version  Part number  Serial number     Description",
                "Chassis                                OPENNV-SYN-0001   MX204 synthetic",
                "Routing Engine 0  REV 01   OPENNV-RE    OPENNV-RE-0001    Routing Engine",
                "FPC 0             REV 01   OPENNV-FPC   OPENNV-FPC-0001   MPC synthetic",
                f"Power Supply 0    REV 01   OPENNV-PSU   {('N/A' if degraded else 'OPENNV-PSU-0001'):<18}{('Faulty' if degraded else 'AC A')}",
            ]
        if platform == "cisco_nxos" and category_name == "hardware":
            return [
                "Mod Ports Module-Type                         Model              Status",
                "--- ----- ----------------------------------- ------------------ ----------",
                "1    48   10/25G Ethernet Module              OPENNV-N9K-48      ok",
                f"2    6    40/100G Ethernet Module            OPENNV-N9K-6       {('faulty' if degraded else 'ok')}",
                "27   0    Supervisor Module                   OPENNV-SUP         active *",
                "Mod  Sw              Hw      Slot",
                "1    synthetic       1.0     LC1",
            ]
        if platform == "cisco_iosxr" and category_name == "hardware":
            return [
                "Node              Type                       State             Config state",
                "--------------------------------------------------------------------------------",
                "0/RP0/CPU0        OPENNV-RP                  IOS XR RUN        NSHUT",
                "0/RP1/CPU0        OPENNV-RP                  IOS XR RUN        NSHUT",
                "0/0/CPU0          OPENNV-LC                  IOS XR RUN        NSHUT",
                f"0/1/CPU0          OPENNV-LC                  {('FAILED' if degraded else 'IOS XR RUN'):<17}NSHUT",
            ]
        if platform == "citrix_adc":
            return [
                "Platform: Citrix ADC virtual appliance (synthetic)",
                "Manufactured on: 2026-08-16",
                "CPU: 8 synthetic vCPU, Memory: 16384 MB",
                "Host ID: OPENNV-SYN-0001",
                f"Hardware health: {('DEGRADED' if degraded else 'OK')}",
                "Done",
            ]
        return [
            "NAME: Chassis, DESCR: OpenNV synthetic network chassis",
            "PID: OPENNV-CHASSIS, VID: V01, SN: OPENNV-SYN-0001",
            "NAME: Power Supply 1, DESCR: Synthetic AC power supply",
            "PID: OPENNV-PSU, VID: V01, SN: OPENNV-PSU-0001",
            f"NAME: Fan Tray 1, DESCR: Synthetic fan tray, STATE: {('faulty' if degraded else 'ok')}",
            f"PID: OPENNV-FAN, VID: V01, SN: {('N/A' if degraded else 'OPENNV-FAN-0001')}",
        ]

    if category_name == "environment":
        if platform == "juniper_junos":
            return [
                "Class Item                           Status     Measurement",
                "Temp  FPC 0 CPU                      OK         39 degrees C / 102 degrees F",
                f"Temp  Routing Engine 0              {('Failed' if degraded else 'OK'):<11}{get_path(inventory, 'environment.temp_c'):.1f} degrees C",
                f"Fans  Fan 1                          {('Failed' if degraded else 'OK'):<11}{('0' if degraded else '7200')} RPM",
                f"Power PEM 0                          {('Failed' if degraded else 'OK'):<11}{('0' if degraded else 'Online')}",
                "Power PEM 1                          OK         Online",
            ]
        if platform == "f5_tmos":
            return [
                "Sys::Hardware: Environmental Sensors",
                "Name                         State      Current Value    Threshold",
                f"/sys/chassis/temp-inlet     {('critical' if degraded else 'good'):<11}{get_path(inventory, 'environment.temp_c'):.1f} C          75.0 C",
                f"/sys/chassis/fan-1          {('failed' if degraded else 'good'):<11}{('0' if degraded else '7200')} RPM        2500 RPM",
                f"/sys/chassis/power-1        {('failed' if degraded else 'good'):<11}{('0' if degraded else '12.1')} V          10.5 V",
                "/sys/chassis/power-2        good       12.0 V          10.5 V",
            ]
        if platform == "citrix_adc":
            return [
                "Environmental status",
                f"1) CPU temperature: {get_path(inventory, 'environment.temp_c'):.1f} C, State: {('CRITICAL' if degraded else 'NORMAL')}",
                f"2) Fan 0 speed: {('0' if degraded else '7200')} RPM, State: {('FAILED' if degraded else 'NORMAL')}",
                f"3) Power supply 0: {('FAILED' if degraded else 'NORMAL')}",
                "4) Power supply 1: NORMAL",
                "Done",
            ]
        return [
            "Sensor                Location          State          Reading",
            f"Inlet temperature     Chassis           {('critical' if degraded else 'ok'):<15}{get_path(inventory, 'environment.temp_c'):.1f} C",
            f"Fan tray 1             Chassis           {('failed' if degraded else 'ok'):<15}{('0' if degraded else '7200')} RPM",
            f"Power supply 1         Chassis           {('failed' if degraded else 'ok'):<15}{('0' if degraded else '12.1')} V",
            "Power supply 2         Chassis           ok             12.0 V",
        ]

    if category_name == "cpu":
        if platform == "juniper_junos":
            return [
                f"last pid: 4031; load averages: {get_path(inventory, 'resources.load_5m'):.2f}, 0.38, 0.31  up 30+04:12:10",
                f"CPU: {get_path(inventory, 'resources.cpu_pct'):.1f}% user, 3.2% system, 0.0% interrupt, {max(0.0, 96.8 - get_path(inventory, 'resources.cpu_pct')):.1f}% idle",
                "Mem: 2048M Active, 1024M Inact, 512M Wired, 4096M Free",
                "PID USERNAME  THR PRI NICE   SIZE    RES STATE    C   TIME   WCPU COMMAND",
                f"911 root       14  52    0  812M   244M {('RUN' if degraded else 'select'):<8}0 112:41 {('88.0' if degraded else '8.2')}% rpd",
                "744 root        8  20    0  422M   110M select   1  48:02  1.4% chassisd",
            ]
        if platform == "f5_tmos":
            return [
                "Sys::Performance System",
                "System CPU Usage                 Current  Average  Max(since 00:00)",
                f"Utilization                       {get_path(inventory, 'resources.cpu_pct'):.1f}%    20.1%    {get_path(inventory, 'resources.cpu_pct'):.1f}%",
                f"Load average (5 minute)            {get_path(inventory, 'resources.load_5m'):.2f}     0.38     {get_path(inventory, 'resources.load_5m'):.2f}",
                f"TMM CPU                            {('96.2' if degraded else '18.4')}%    17.9%    {('99.1' if degraded else '31.0')}%",
                "Analysis plane                     1.4%     1.1%     2.0%",
            ]
        if platform == "arista_eos":
            return [
                f"top - 07:00:00 up 30 days, load average: {get_path(inventory, 'resources.load_5m'):.2f}, 0.38, 0.31",
                "Tasks: 143 total, 1 running, 142 sleeping, 0 stopped, 0 zombie",
                f"%Cpu(s): {get_path(inventory, 'resources.cpu_pct'):.1f} us, 3.2 sy, 0.0 ni, 0.0 wa, 0.0 hi, 0.0 si",
                "PID USER       PR NI    VIRT    RES S %CPU %MEM     TIME+ COMMAND",
                f"911 root       20  0  812000 244000 {('R' if degraded else 'S')} {('88.0' if degraded else '8.2')}  3.0 112:41.00 ProcMgr",
                "744 root       20  0  422000 110000 S  1.4  1.3  48:02.00 Rib",
            ]
        return [
            "CPU utilization for five seconds: synthetic; one minute: synthetic; five minutes: synthetic",
            "PID    Runtime(ms) Invoked  uSecs  5Sec   1Min   5Min  TTY Process",
            f"101          9234   44211    208  {get_path(inventory, 'resources.cpu_pct'):>5.1f}%  20.0%  18.0%   0 Routing",
            "202          4401   88120     49   1.2%   1.0%   0.9%   0 Interface",
            f"303          1182   22300     53  {('71.0' if degraded else '0.2')}%   0.2%   0.1%   0 SyntheticWorker",
        ]

    if category_name in {"memory", "system_stats"}:
        if category_name == "system_stats" and platform == "citrix_adc":
            return [
                "NetScaler system statistics",
                "Metric                              Value        Rate (/s)",
                f"CPU utilization                    {get_path(inventory, 'resources.cpu_pct'):.1f}%        -",
                f"Memory utilization                 {get_path(inventory, 'resources.memory_used_pct'):.1f}%        -",
                f"Current client connections          {get_path(inventory, 'resources.active_connections')}         -",
                f"HTTP requests                       1284231      {('42000' if degraded else '8421')}",
                f"Packet drops                        {('9312' if degraded else '0')}            {('152' if degraded else '0')}",
                "Done",
            ]
        if platform == "juniper_junos":
            return [
                "System memory usage distribution:",
                "Item                         Total (MB)   Used (MB)   Utilization",
                f"Routing engine memory             8192        {8064 if degraded else 3990:<11}{get_path(inventory, 'resources.memory_used_pct'):.1f}%",
                "Kernel memory                 1024         512         50.0%",
                "Routing protocol memory       2048         912         44.5%",
                f"Free memory: {get_path(inventory, 'resources.memory_free_mb')} MB",
            ]
        if platform == "f5_tmos":
            return [
                "Sys::Memory",
                "Memory                         Total   Used    Free    Used%",
                f"Host memory                    8192M   {8064 if degraded else 3990:<7}{get_path(inventory, 'resources.memory_free_mb')}M    {get_path(inventory, 'resources.memory_used_pct'):.1f}%",
                "TMM memory                     4096M   2048M   2048M   50.0%",
                "Swap                           2048M   0M      2048M    0.0%",
                f"Provisioning warning           {('critical' if degraded else 'none')}",
            ]
        if platform == "cisco_nxos":
            return [
                "Load average: 1 minute: 0.31 5 minutes: 0.42 15 minutes: 0.38",
                "Processes   : 143 total, 1 running",
                f"CPU states  : {('98.1' if degraded else '22.4')}% user, 3.2% kernel, 0.0% idle",
                f"Memory usage: 8192M total, {8064 if degraded else 3990}M used, {get_path(inventory, 'resources.memory_free_mb')}M free",
                "Kernel memory: 1024M, Page cache: 512M",
            ]
        if platform == "cisco_iosxr":
            return [
                "Physical Memory: 8192M total",
                "Application Memory: 7168M total",
                f"Image: 1024M, Reserved: 512M, Allocated: {8064 if degraded else 3990}M, Free: {get_path(inventory, 'resources.memory_free_mb')}M",
                f"Memory utilization: {get_path(inventory, 'resources.memory_used_pct'):.1f}%",
                "Top consumers: fib_mgr 512M, bgp 384M, ospf 128M",
            ]
        return [
            "Memory statistics (synthetic)",
            "Pool             Total(MB)  Used(MB)  Free(MB)  Used%",
            f"System               8192      {8064 if degraded else 4096:<8}{get_path(inventory, 'resources.memory_free_mb') if category_name == 'memory' else 4920:<10}{get_path(inventory, 'resources.memory_used_pct'):.1f}%",
            "Packet buffers       1024         384       640   37.5%",
            "Control plane        2048         912      1136   44.5%",
        ]

    if category_name == "logging":
        if platform == "f5_tmos":
            return [
                "Sys::Log LTM (last records)",
                "Aug 16 07:00:01 demo-f5-tmos-01 info tmm: virtual /Common/app_https health poll complete",
                "Aug 16 07:00:04 demo-f5-tmos-01 warning mcpd: synthetic utilization threshold crossed",
                f"Aug 16 07:00:07 demo-f5-tmos-01 {('crit' if degraded else 'info')} sod: {get_path(inventory, 'logging.last_event')}",
                f"Aug 16 07:00:09 demo-f5-tmos-01 warning logger: critical={get_path(inventory, 'logging.critical_count')} warning={get_path(inventory, 'logging.warning_count')}",
            ]
        if platform == "juniper_junos":
            return [
                "Aug 16 07:00:01 demo-juniper-junos-01 rpd[911]: RPD_BGP_NEIGHBOR_STATE_CHANGED: BGP peer 192.0.2.2 Up",
                "Aug 16 07:00:04 demo-juniper-junos-01 mib2d[744]: SNMP_TRAP_LINK_DOWN: ifIndex 533",
                f"Aug 16 07:00:07 demo-juniper-junos-01 chassisd[701]: {('CHASSISD_TEMP_HOT_NOTICE' if degraded else 'CHASSISD_SNMP_TRAP10')}: {get_path(inventory, 'logging.last_event')}",
                f"Aug 16 07:00:09 demo-juniper-junos-01 eventd[602]: synthetic summary critical={get_path(inventory, 'logging.critical_count')} warning={get_path(inventory, 'logging.warning_count')}",
                "--- last 50 records requested; representative fixture rows shown ---",
            ]
        if platform == "citrix_adc":
            return [
                "1) 2026-08-16 07:00:01 GMT INFO SYSTEM health poll completed",
                "2) 2026-08-16 07:00:04 GMT WARNING INTERFACE synthetic utilization threshold crossed",
                f"3) 2026-08-16 07:00:07 GMT {('CRITICAL' if degraded else 'INFO')} HA {get_path(inventory, 'logging.last_event')}",
                f"4) 2026-08-16 07:00:09 GMT WARNING SUMMARY critical={get_path(inventory, 'logging.critical_count')} warning={get_path(inventory, 'logging.warning_count')}",
                "Done",
            ]
        return [
            "Log Buffer (synthetic):",
            "Aug 16 07:00:01 INFO  SYSTEM: health poll completed",
            "Aug 16 07:00:04 WARN  INTERFACE: synthetic utilization threshold crossed",
            f"Aug 16 07:00:07 {('CRIT' if degraded else 'INFO'):<5} HA: {get_path(inventory, 'logging.last_event')}",
            f"Aug 16 07:00:09 WARN  SUMMARY: critical={get_path(inventory, 'logging.critical_count')} warning={get_path(inventory, 'logging.warning_count')}",
        ]

    if category_name == "clock":
        return [
            "Time source is NTP",
            f"Clock state: {('unsynchronized' if degraded else 'synchronized')}",
            "Reference clock: 192.0.2.123",
            f"Reference status: {('unreachable' if degraded else 'reachable')}",
            "Timezone: UTC (offset 0 seconds)",
        ]

    if category_name == "config_state":
        if identifier == "show_running_config_hostname":
            return [
                "Building configuration...",
                "Current configuration : 42 bytes",
                "!",
                f"hostname {inventory['hostname']}",
                "!",
                "end",
            ]
        if identifier == "show_archive_config_differences":
            return [
                "Contextual Config Diffs:",
                f"{('! Candidate archive differs from running configuration' if degraded else '! No changes were found')}",
                f"{('-interface GigabitEthernet1/0/2' if degraded else '! Running and startup configuration are aligned')}",
                f"{('+ shutdown' if degraded else '! Archive comparison complete')}",
                "End of Config Diffs",
            ]
        if identifier == "show_checkpoint_summary":
            return [
                "Checkpoint Summary",
                "Name                         Created by       Created at             Status",
                "baseline-20260816            opennv-fixture   2026-08-16 06:40:00    complete",
                f"candidate-20260816           opennv-fixture   2026-08-16 06:58:00    {('pending' if degraded else 'complete')}",
                f"Rollback required: {('yes' if degraded else 'no')}",
            ]
        if identifier == "show_system_commit":
            return [
                "0   2026-08-16 06:41:22 UTC by opennv-fixture via cli",
                "    commit confirmed, synthetic baseline",
                f"1   2026-08-16 06:58:10 UTC by opennv-fixture via cli {('(pending)' if degraded else '')}".rstrip(),
                f"    {('candidate change awaiting confirmation' if degraded else 'health policy update')}",
                "2   2026-08-15 18:04:02 UTC by opennv-fixture via netconf",
            ]
        if platform == "citrix_adc" and identifier == "show_ns_mode":
            return [
                "Mode                 Status",
                "-------------------  --------",
                "Layer 3              ON",
                "Edge Configuration   OFF",
                f"MBF                  {('ON (pending restart)' if degraded else 'OFF')}",
                "USNIP                ON",
                "Done",
            ]
        if platform == "citrix_adc" and identifier == "show_ns_runningconfig":
            return [
                "# Citrix ADC synthetic running configuration",
                "set ns config -IPAddress 192.0.2.10 -netmask 255.255.255.0",
                "add lb vserver app-primary HTTP 192.0.2.100 80",
                "bind lb vserver app-primary app-service-01",
                f"# configuration state: {('candidate changes present' if degraded else 'clean')}",
                "Done",
            ]
        return [
            "Configuration state",
            f"  Candidate differs from running: {('yes' if degraded else 'no')}",
            f"  Last operation: {get_path(inventory, 'config.last_change_id')}",
            "  User: opennv-fixture",
            f"  Commit status: {('pending' if degraded else 'complete')}",
        ]

    if category_name == "health":
        if platform == "juniper_junos":
            return [
                f"{get_path(inventory, 'health.open_alerts')} alarms currently active",
                "Alarm time               Class  Description",
                f"2026-08-16 07:00:07 UTC  {('Major' if degraded else 'Info'):<7}{('FPC 0 temperature threshold exceeded' if degraded else 'No active chassis alarms')}",
                f"Craft interface alarm LED: {('red' if degraded else 'off')}",
                f"Chassis health: {get_path(inventory, 'health.status')}",
            ]
        return [
            f"Alarm status: {get_path(inventory, 'health.status').upper()}",
            f"Active alarms: {get_path(inventory, 'health.open_alerts')}",
            f"System health score: {get_path(inventory, 'health.score')}/100",
            f"Routing engine: {('degraded' if degraded else 'operational')}",
            f"Forwarding plane: {('degraded' if degraded else 'operational')}",
        ]

    if category_name in {"lb_virtual", "lb_pool", "lb_member", "lb_monitor", "lb_server"}:
        if platform == "f5_tmos":
            if category_name == "lb_virtual":
                return [
                    "Ltm::Virtual Server: /Common/app_https",
                    f"  Availability     : {unavailable}",
                    f"  State            : {disabled}",
                    "  Destination      : /Common/192.0.2.100:443",
                    "  Ip Protocol      : tcp",
                    "  Ltm::Pool        : /Common/app_pool",
                    "  Profiles         : /Common/tcp, /Common/clientssl, /Common/http",
                    "  Source Address Translation: automap",
                ]
            if category_name == "lb_pool":
                return [
                    "Ltm::Pool: /Common/app_pool",
                    f"  Availability     : {unavailable}",
                    f"  State            : {disabled}",
                    "  Load Balancing Mode : least-connections-member",
                    f"  Active Member Count : {2 if degraded else 4}",
                    "  Total Member Count  : 4",
                    "  Monitor          : /Common/app_http",
                    "  Service Down Action: none",
                ]
            if category_name == "lb_member":
                expected_drain = not degraded and get_path(inventory, "load_balancing.members_down") == 1
                return [
                    "Ltm::Pool: /Common/app_pool",
                    "  Ltm::Pool Member: /Common/10.0.0.20:8080",
                    f"    Availability   : {unavailable}",
                    f"    State          : {disabled}",
                    "    Monitor Status : synthetic app_http",
                    "  Ltm::Pool Member: /Common/10.0.0.21:8080",
                    f"    Availability   : {('offline (expected drain)' if expected_drain else 'available')}",
                    f"    State          : {('user-disabled' if expected_drain else 'enabled')}",
                ]
            if category_name == "lb_monitor":
                return [
                    "Ltm::Monitor: /Common/app_http",
                    "  Type             : http",
                    "  Interval         : 5",
                    "  Timeout          : 16",
                    "  Send String      : GET /health HTTP/1.1",
                    f"  Last Result      : {('connection refused' if degraded else 'HTTP/1.1 200 OK')}",
                    f"  Failing Instances: {get_path(inventory, 'load_balancing.monitors_failing')}",
                ]
            return [
                "Ltm::Node: /Common/app-node-01",
                f"  Availability     : {unavailable}",
                f"  State            : {disabled}",
                "  Address          : 10.0.0.20",
                "  Monitor          : /Common/app_icmp",
                "Ltm::Node: /Common/app-node-02",
                "  Availability     : available",
                "  State            : enabled",
            ]
        if identifier == "stat_lb_vserver":
            return [
                "Virtual Server   State  Requests  Responses  Current Clients  SurgeQ",
                f"app-primary      {bad.upper():<6}1284231   1284202    1842             {('48' if degraded else '0')}",
                "app-secondary    UP    884201    884190     921              0",
                "api-primary      UP    422109    422100     438              0",
                "Done",
            ]
        label = {
            "lb_virtual": "lb vserver app-primary",
            "lb_pool": "serviceGroup app-pool HTTP",
            "lb_member": "service app-member-01 10.0.0.20 HTTP 8080",
            "lb_monitor": "lb monitor app-http HTTP",
            "lb_server": "server app-node-01 10.0.0.20",
        }[category_name]
        return [
            f"1) {label}",
            f"   State: {bad.upper()}, Effective State: {bad.upper()}",
            f"   Health: {('0' if degraded else '100')}, Monitor State: {('FAILED' if degraded else 'UP')}",
            "2) synthetic secondary object",
            "   State: UP, Effective State: UP, Health: 100",
            "Done",
        ]

    if category_name == "storage":
        return [
            "Sys::Disk",
            "Filesystem                  Size  Used  Avail  Use%  Mounted on",
            f"/dev/mapper/vg--db           20G   {('19G' if degraded else '8G'):<5}{('1G' if degraded else '12G'):<7}{get_path(inventory, 'storage.max_used_pct'):.1f}%  /var/lib/mysql",
            "/dev/mapper/vg--log          10G    3G     7G   30.0%  /var/log",
            "/dev/mapper/vg--config        4G    1G     3G   25.0%  /config"
            + (" (read-only)" if degraded else ""),
        ]

    raise ValueError(f"no record layout for category: {category_name}")


def cli_body(platform: str, identifier: str, category_name: str) -> str:
    """Return a vendor-shaped template body with normalized metric placeholders."""

    if category_name == "system_version":
        if platform == "f5_tmos":
            return "${records}\n  Version     ${os_version}\n  BaseBuild   ${image}\nUptime: ${uptime}\nOperating state: ${oper_state}"
        if platform == "citrix_adc":
            return "NetScaler NS version: ${os_version}\nBuild image: ${image}\n${records}\nUptime: ${uptime}\nOperating state: ${oper_state}"
        return "${records}\nSoftware version: ${os_version}\nSystem image file: ${image}\nSystem uptime: ${uptime}\nOperating state: ${oper_state}"
    if category_name == "interface_summary":
        header = {
            "juniper_junos": "Interface               Admin Link Proto    Local                 Remote",
            "f5_tmos": "Net::Interface\nName       Admin   Status    Speed  Duplex  Flow Ctrl",
            "citrix_adc": "Interface summary\nID   Admin Link    Speed  Duplex MAC",
            "cisco_nxos": "--------------------------------------------------------------------------------\nPort          Name             Type  Speed   MTU   Status",
            "cisco_iosxr": "Interface            IP-Address      Status          Protocol Vrf-Name",
        }.get(platform, "Interface              IP-Address      OK? Method Status                Protocol")
        return f"{header}\n${{records}}\nSummary: ${{total}} interfaces, ${{up}} up, ${{down}} down"
    if category_name == "interface_detail":
        return "${records}\n  MTU ${mtu} bytes\n  Peak utilization ${utilization}\n  Aggregate input/output errors ${error_count}"
    if category_name == "routes":
        return "${records}\nRoute summary: ${route_total} total, ${stale} stale\nDefault route present: ${default_present}"
    if category_name == "arp":
        return "${records}\nTotal entries: ${entries}\nIncomplete entries: ${incomplete}"
    if category_name == "mac":
        return "${records}\nTotal Mac Addresses for this criterion: ${entries}\nDynamic entries: ${dynamic}"
    if category_name == "neighbors":
        if platform == "citrix_adc" and identifier == "show_ns_ip":
            return (
                "${records}\nConfigured NS/SNIP addresses: ${count}\n"
                "Expected configured addresses: ${expected}\nInventory set matched: ${expected_matches}"
            )
        return "${records}\nTotal entries displayed: ${count}\nExpected entries: ${expected}\nExpected set matched: ${expected_matches}"
    if category_name == "vlans":
        return "${records}\nVLAN summary: ${total} defined, ${active} active"
    if category_name == "aggregation":
        return "${records}\nAggregate summary: ${total} total, ${up} operational, ${down} down"
    if category_name == "routing_peers":
        return "${records}\nPeer summary: ${established}/${peers} established (${ratio})"
    if category_name == "redundancy":
        return "${records}\nLocal state: ${state}\nPeer state: ${peer}\nRedundancy ready: ${ready}"
    if category_name == "hardware":
        return "${records}\nHardware summary: ${ok}/${modules} healthy, ${faulty} faulty"
    if category_name == "environment":
        return "${records}\nPeak temperature: ${temperature} C\nFans healthy: ${fans_ok}\nPower supplies healthy: ${psus_ok}"
    if category_name == "cpu":
        return "${records}\nCPU utilization: ${cpu}\nFive-minute load: ${load}"
    if category_name == "memory":
        return "${records}\nMemory used: ${memory}\nMemory free: ${free_mb} MB"
    if category_name == "logging":
        return "${records}\nMessage summary: ${critical} critical, ${warnings} warning\nLast event: ${last_event}"
    if category_name == "clock":
        return "${records}\nCurrent time: ${clock}\nSynchronized: ${synced}\nOffset: ${offset} ms"
    if category_name == "inventory":
        return "${records}\nInventory summary: ${components} components, ${missing_serials} missing serials\nChassis serial: ${serial}"
    if category_name == "config_state":
        return "${records}\nConfiguration clean: ${clean}\nLast change: ${change}\nConfiguration age: ${age} minutes"
    if category_name == "health":
        return "${records}\nHealth status: ${status}\nHealth score: ${score}\nOpen alerts: ${open_alerts}"
    if category_name == "lb_virtual":
        return "${records}\nVirtual server summary: ${available}/${virtuals} available, ${unavailable} unavailable"
    if category_name == "lb_pool":
        return "${records}\nPool summary: ${available}/${pools} available, ${unavailable} unavailable"
    if category_name == "lb_member":
        return "${records}\nMember summary: ${up}/${members} up, ${down} down"
    if category_name == "lb_monitor":
        return "${records}\nMonitor summary: ${enabled}/${monitors} enabled, ${failing} failing"
    if category_name == "lb_server":
        return "${records}\nServer summary: ${up}/${servers} up, ${down} down"
    if category_name == "ha_sync":
        return "${records}\nLocal state: ${state}\nConfiguration synchronized: ${synced}\nHA ready: ${ready}"
    if category_name == "storage":
        return "${records}\nFilesystem summary: ${filesystems} filesystems, max used ${max_used}, ${readonly} read-only"
    if category_name == "system_stats":
        return "${records}\nCPU utilization: ${cpu}\nMemory used: ${memory}\nActive connections: ${connections}"
    raise ValueError(f"no CLI body for category: {category_name}")


def build_definition(platform: str, platform_data: dict[str, Any], command_row: tuple[str, str, str]) -> dict[str, Any]:
    identifier, command, category_name = command_row
    category = CATEGORIES[category_name]
    variables: dict[str, Any] = {
        "hostname": {"source": "inventory.hostname"},
        "command": {"literal": command},
    }
    inventory: dict[str, Any] = {"hostname": f"demo-{platform.replace('_', '-')}-01"}
    result_schema: list[dict[str, Any]] = []
    for variable, source, healthy, value_type, result_path, label, generator in category["fields"]:
        variables[variable] = variable_rule(source, generator)
        set_path(inventory, source, healthy)
        result_schema.append({"path": result_path, "type": value_type, "source": f"inventory.{source}"})
    if category_name == "system_version":
        version, image = PLATFORM_SYSTEM_FIXTURES[platform]
        set_path(inventory, "system.os_version", version)
        set_path(inventory, "system.image", image)
    variables["records"] = {
        "generator": {
            "name": "join",
            "source": "inventory.display.records",
            "separator": "\n",
        }
    }
    set_path(inventory, "display.records", record_lines(platform, identifier, command, category_name, inventory))
    if command.lower().startswith("show"):
        command_alias = "sh" + command[4:]
    elif command.lower().startswith("stat"):
        command_alias = command + " -fullValues"
    else:
        command_alias = command + " --brief"
    template = platform_data["prompt"] + "\n" + cli_body(platform, identifier, category_name) + "\n"
    definition: dict[str, Any] = {
        "apiVersion": "opennv.io/v1alpha1",
        "kind": "OutputFSM",
        "metadata": {
            "id": identifier,
            "title": f"{platform_data['name']} — {command}",
            "description": (
                f"Deterministic synthetic, vendor-shaped response for {command} on "
                f"{platform_data['name']}; not captured output."
            ),
            "license": "Apache-2.0",
            "synthetic": True,
            "category": category_name,
        },
        "spec": {
            "platform": platform,
            "platform_aliases": platform_data["aliases"],
            "command": command,
            "aliases": [command_alias],
            "variables": variables,
            "template": template,
            "result_schema": result_schema,
            "fixtures": [],
        },
    }
    healthy_fixture = {
        "name": "healthy",
        "description": (
            "Synthetic deterministic healthy baseline with representative records; "
            "not captured from vendor equipment."
        ),
        "inventory": inventory,
        "expected_output": render(definition, inventory),
        "expected_result": normalized_result(definition, inventory),
    }
    degraded = degraded_inventory(category_name, inventory)
    set_path(degraded, "display.records", record_lines(platform, identifier, command, category_name, degraded))
    degraded_fixture = {
        "name": "degraded",
        "description": (
            "Synthetic deterministic degraded scenario designed to fail the catalog validation hint; "
            "not captured from vendor equipment."
        ),
        "inventory": degraded,
        "expected_output": render(definition, degraded),
        "expected_result": normalized_result(definition, degraded),
    }
    definition["spec"]["fixtures"].extend([healthy_fixture, degraded_fixture])
    return definition


def main() -> int:
    packs_root = ROOT / "packs"
    if packs_root.exists():
        for platform_dir in packs_root.iterdir():
            if platform_dir.is_dir():
                shutil.rmtree(platform_dir)
    index: dict[str, Any] = {
        "apiVersion": "opennv.io/v1alpha1",
        "kind": "OutputFSMCatalog",
        "metadata": {"name": "opennv-core", "synthetic": True, "license": "Apache-2.0"},
        "platforms": [],
    }
    for platform, platform_data in PLATFORMS.items():
        command_dir = packs_root / platform / "commands"
        command_dir.mkdir(parents=True, exist_ok=True)
        platform_index: dict[str, Any] = {
            "id": platform,
            "name": platform_data["name"],
            "aliases": platform_data["aliases"],
            "commands": [],
        }
        for row in platform_data["commands"]:
            definition = build_definition(platform, platform_data, row)
            identifier, command, category_name = row
            with (command_dir / f"{identifier}.yaml").open("w", encoding="utf-8") as handle:
                yaml.dump(
                    definition,
                    handle,
                    Dumper=LiteralSafeDumper,
                    sort_keys=False,
                    width=110,
                    allow_unicode=True,
                )
            validation_path, operator, expected, failed = CATEGORIES[category_name]["validation"]
            platform_index["commands"].append({
                "id": identifier,
                "command": command,
                "aliases": definition["spec"]["aliases"],
                "definition": f"packs/{platform}/commands/{identifier}.yaml",
                "result_paths": [field["path"] for field in definition["spec"]["result_schema"]],
                "validation_hint": {
                    "path": validation_path,
                    "operator": operator,
                    "expected": expected,
                    "failure_example": failed,
                },
            })
        with (packs_root / platform / "index.yaml").open("w", encoding="utf-8") as handle:
            yaml.safe_dump(platform_index, handle, sort_keys=False, width=110, allow_unicode=True)
        index["platforms"].append(platform_index)
    (ROOT / "catalog").mkdir(exist_ok=True)
    with (ROOT / "catalog" / "index.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(index, handle, sort_keys=False, width=110, allow_unicode=True)
    print(f"generated {sum(len(item['commands']) for item in index['platforms'])} definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
