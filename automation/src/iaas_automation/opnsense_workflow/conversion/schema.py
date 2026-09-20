"""Field vocabulary and native expressibility policy; no I/O."""
from typing import Any

_STANDARD_FIELDS: dict[str, tuple[str, ...]] = {
    "aliases": ("name", "type", "content", "description", "enabled", "updatefreq_days"),
    "vips": ("description", "interface", "address", "bind", "expand"),
    "gateways": (
        "name", "interface", "ip_protocol", "gateway", "default_gw", "far_gw",
        "monitor_disable", "monitor_noroute", "monitor", "force_down", "latency_low",
        "latency_high", "loss_low", "loss_high", "interval", "time_period",
        "loss_interval", "data_length", "priority", "weight", "description",
    ),
    "filter-rules": (
        "scope", "slug", "enabled", "sequence", "interface", "direction", "action",
        "quick", "ip_protocol", "protocol", "source_net", "destination_net",
        "source_invert", "source_port", "destination_invert", "destination_port", "gateway", "log",
    ),
    "dnat": (
        "scope", "slug", "enabled", "sequence", "interface", "ip_protocol", "protocol",
        "source_net", "destination_net", "target", "nat_reflection", "associated_rule",
        "source_port", "destination_port", "local_port", "source_invert", "destination_invert",
        "log", "pool_opts", "tag", "tagged",
    ),
    "one-to-one-nat": (
        "scope", "slug", "enabled", "sequence", "interface", "type", "external", "source_net",
        "destination_net", "nat_reflection", "source_invert", "destination_invert", "log",
    ),
    "interface-groups": ("name", "members", "gui_group", "sequence", "description"),
}

_DEFAULTS: dict[str, dict[str, Any]] = {
    "filter-rules": {
        "source_invert": False, "destination_invert": False, "log": True,
    },
    "dnat": {
        "source_port": "", "destination_port": "", "local_port": "", "source_invert": False,
        "destination_invert": False, "log": False, "pool_opts": "", "tag": "", "tagged": "",
    },
    "one-to-one-nat": {"source_invert": False, "destination_invert": False, "log": False},
    "interface-groups": {"description": ""},
}

_LIST_FIELDS = {
    "aliases": {"content"},
    "vips": set(),
    "gateways": set(),
    "filter-rules": {"interface"},
    "dnat": {"interface"},
    "one-to-one-nat": set(),
    "interface-groups": {"members"},
}

_BOOL_FIELDS = {
    "enabled", "bind", "expand", "default_gw", "far_gw", "monitor_disable", "monitor_noroute",
    "force_down", "quick", "source_invert", "destination_invert", "log", "gui_group",
}

# Names emitted by the Collection's simplify_translate layer and the common
# nested names of its native API responses.  Canonical Collection output uses
# the left hand side already; accepting the right hand side makes the adapter
# useful with representative raw response fixtures without exposing those
# raw fields in its result.
_FIELD_ALIASES = {
    "descr": "description", "ifname": "interface", "ipprotocol": "ip_protocol",
    "defaultgw": "default_gw", "fargw": "far_gw", "latencylow": "latency_low",
    "latencyhigh": "latency_high", "losslow": "loss_low", "losshigh": "loss_high",
    "disabled": "enabled", "nobind": "bind", "noexpand": "expand", "nogroup": "gui_group",
    "natreflection": "nat_reflection", "pass": "associated_rule", "nordr": "no_port_forward",
    "source_not": "source_invert", "destination_not": "destination_invert",
    "updatefreq": "updatefreq_days", "source-port": "source_port", "destination-port": "destination_port",
    "local-port": "local_port", "target-port": "target_port", "poolopts": "pool_opts", "no-nat": "no_nat",
    "interfacenot": "interface_invert", "disablereplyto": "disable_replyto", "allowopts": "allow_opts",
    "statetype": "state_type", "state-policy": "state_policy", "statetimeout": "state_timeout",
    "max": "max_states", "max-src-nodes": "max_src_nodes", "max-src-states": "max_src_states",
    "max-src-conn": "max_src_conn", "max-src-conn-rate": "max_src_conn_rate", "max-src-conn-rates": "max_src_conn_rates",
    "adaptivestart": "adaptive_start", "adaptiveend": "adaptive_end", "set-prio": "set_prio",
    "set-prio-low": "set_prio_low", "tcpflags1": "tcp_flags", "tcpflags2": "tcp_flags_clear",
    "sched": "schedule", "icmptype": "icmp_type", "icmp6type": "icmpv6_type", "divert-to": "divert_to",
    "advbase": "advertising_base", "advskew": "advertising_skew",
}

_SELECT_FIELDS = {
    "type", "interface", "mode", "vhid", "advertising_base", "advertising_skew", "action", "direction",
    "ip_protocol", "protocol", "gateway", "replyto", "state_type", "state_policy", "overload", "prio",
    "set_prio", "set_prio_low", "schedule", "tos", "members", "nat_reflection", "pool_opts", "associated_rule",
    "icmp_type", "icmpv6_type", "tcp_flags", "tcp_flags_clear", "received-on",
    "divert_to", "shaper1", "shaper2", "authtype", "proto",
}

_INVERTED_FIELDS = {"disabled": "enabled", "nobind": "bind", "noexpand": "expand", "nogroup": "gui_group"}

# Provider fields which carry configuration semantics but are deliberately
# outside this workflow's standard schema. UUIDs and transport metadata are
# intentionally absent so irrelevant native fields do not reject a row.
_NATIVE_UNEXPRESSED: dict[str, set[str]] = {
    "aliases": {"interface", "path_expression", "authtype", "proto", "counters"},
    "vips": {"mode", "gateway", "password", "vhid", "advertising_base", "advertising_skew", "peer", "peer6", "nosync"},
    "gateways": {"nosync", "monitor_killstates", "monitor_killstates_priority"},
    "filter-rules": {"interface_invert", "tag", "tagged", "replyto", "disable_replyto", "allow_opts",
                      "state_type", "state_policy", "state_timeout", "max_states", "max_src_nodes",
                      "max_src_states", "max_src_conn", "max_src_conn_rate", "max_src_conn_rates",
                      "overload", "adaptive_start", "adaptive_end", "prio", "set_prio", "set_prio_low",
                      "tcp_flags", "tcp_flags_clear", "schedule", "tos", "icmp_type", "icmpv6_type", "divert_to",
                      "shaper1", "shaper2", "received-on", "received-on-not", "tcpflags_any",
                      "nosync", "nopfsync"},
    "dnat": {"target_port", "no_nat", "nosync"},
    "one-to-one-nat": {"nosync"},
    "interface-groups": set(),
}

# Volatile model fields, scoped to the resource that defines them.
_NATIVE_METADATA = {
    "aliases": {"current_items", "eval_match", "eval_nomatch", "in_block_b", "in_block_p",
                "in_pass_b", "in_pass_p", "out_block_b", "out_block_p", "out_pass_b", "out_pass_p"},
    "filter-rules": {"sort_order", "prio_group", "%source_net", "%destination_net"},
}
_NATIVE_FALSE_FIELDS = {"nosync", "nopfsync", "monitor_killstates", "monitor_killstates_priority",
                        "received-on-not", "tcpflags_any", "counters"}

_IGNORED_NATIVE_FIELDS = {
    "uuid", "id", "created", "updated", "modified", "timestamp", "selected", "key", "value",
    "network", "subnet", "subnet_bits", "source", "destination", "source_not", "destination_not",
    "packets", "bytes", "evaluations", "states", "last_updated",
    "disabled", "nobind", "noexpand", "nogroup", "ifname", "descr", "ipprotocol", "defaultgw", "fargw",
    "latencylow", "latencyhigh", "losslow", "losshigh", "natreflection", "pass", "nordr",
}

_INTEGER_FIELDS = {
    "sequence", "latency_low", "latency_high", "loss_low", "loss_high", "interval", "time_period",
    "loss_interval", "data_length", "priority", "weight", "state_timeout",
}
