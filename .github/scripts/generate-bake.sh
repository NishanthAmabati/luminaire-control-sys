#!/usr/bin/env bash
# Generates Docker bake HCL file for building services
# Usage: generate-bake.sh <environment> <services> <output_file> [config_path]
#
# Services: comma-separated list (e.g., "web,gateway" or "all" or "python")
#   Valid: web, gateway, state, scheduler, timer, metrics, luminaire, python, all
#
# config.yaml is the source of truth - NO DEFAULTS OR FALLBACKS
# Script will fail with clear error if required config value is missing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/../config"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENVIRONMENT="${1:-dev}"
SERVICES_INPUT="${2:-all}"
OUTPUT_FILE="${3:-docker-bake.hcl}"
CONFIG_PATH="${4:-$ROOT_DIR/config.yaml}"
SERVICES_DEF="$CONFIG_DIR/services.yaml"
GENERATE_PY="$SCRIPT_DIR/_generate_bake.py"

# Validate required files exist
if [[ ! -f "$CONFIG_PATH" ]]; then
    echo "ERROR: Config file not found: $CONFIG_PATH" >&2
    exit 1
fi

if [[ ! -f "$SERVICES_DEF" ]]; then
    echo "ERROR: Services definition not found: $SERVICES_DEF" >&2
    exit 1
fi

# HOST_REWRITE: Convert localhost/0.0.0.0 to Docker service names
HOST_REWRITE="${HOST_REWRITE:-1}"
if [[ "$CONFIG_PATH" == *"config-dev.yaml"* ]]; then
    HOST_REWRITE=0
fi

# Git/Registry Info
GIT_SHA="${GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo 'local')}"
GIT_BRANCH="${GIT_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'local')}"
REGISTRY="${DOCKER_REGISTRY:-docker.io}"
USERNAME="${DOCKER_USERNAME:-}"

if [[ "$ENVIRONMENT" == "dev" ]]; then
    REPO_SUFFIX="-dev"
else
    REPO_SUFFIX=""
fi

# ============================================================
# Python Generator Script
# ============================================================

cat > "$GENERATE_PY" << 'PYEOF'
#!/usr/bin/env python3
import yaml
import sys
import re

def get_nested(data, path):
    """Get nested value from dict using dot notation path."""
    parts = [p for p in path.strip('.').split('.') if p]
    cur = data
    for p in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
        if cur is None:
            return None
    return cur

def replace_host(url, host):
    """Replace localhost/0.0.0.0 with Docker service name."""
    if not url:
        return url
    pattern = r'^(http|https|redis)://([^/]+)(.*)$'
    match = re.match(pattern, url)
    if not match:
        return url
    
    proto, hostport, rest = match.groups()
    hostpart = hostport.split(':')[0]
    portpart = ':' + hostport.split(':', 1)[1] if ':' in hostport else ''
    
    if hostpart in ('localhost', '127.0.0.1', '0.0.0.0'):
        return f"{proto}://{host}{portpart}{rest}"
    return url

def parse_services_input(input_str):
    """Parse service selection string."""
    services = [s.strip() for s in input_str.split(',')]
    result = []
    is_all = 'all' in services
    is_python = 'python' in services
    
    for svc in services:
        if svc in ('all', 'python', ''):
            continue
        if svc not in ('web', 'gateway', 'state', 'scheduler', 'timer', 'metrics', 'luminaire'):
            print(f"ERROR: Unknown service '{svc}'. Valid: all, python, web, gateway, state, scheduler, timer, metrics, luminaire", file=sys.stderr)
            sys.exit(1)
        result.append(svc)
    
    if is_all:
        return 'web,gateway,state,scheduler,timer,metrics,luminaire'
    elif is_python:
        return 'state,scheduler,timer,metrics,luminaire'
    return ','.join(result)

def resolve_arg_value(arg_spec, config_data, host_rewrite):
    """Resolve argument value based on spec type. Returns (value, error)."""
    arg_type = arg_spec.get('type')
    
    if arg_type == 'static':
        return arg_spec.get('value', ''), None
    
    elif arg_type == 'config':
        path = arg_spec.get('path')
        if not path:
            return None, f"Missing config path for argument"
        value = get_nested(config_data, path)
        if value is None:
            return None, f"Missing config value '{path}'"
        rewrite_host = arg_spec.get('rewrite_host')
        if rewrite_host and host_rewrite:
            value = replace_host(str(value), rewrite_host)
        return value, None
    
    elif arg_type == 'config_list':
        path = arg_spec.get('path')
        if not path:
            return None, f"Missing config path for argument"
        value = get_nested(config_data, path)
        if not isinstance(value, list):
            return None, f"Expected list at '{path}'"
        return ','.join(str(v) for v in value if v is not None), None
    
    return None, f"Unknown type '{arg_type}'"

def generate_bake():
    config_path = sys.argv[1]
    services_def_path = sys.argv[2]
    services_input = sys.argv[3]
    output_file = sys.argv[4]
    git_sha = sys.argv[5]
    git_branch = sys.argv[6]
    registry = sys.argv[7]
    username = sys.argv[8]
    repo_suffix = sys.argv[9]
    host_rewrite = sys.argv[10] == '1'
    
    # Load YAML files
    with open(config_path) as f:
        config_data = yaml.safe_load(f) or {}
    
    with open(services_def_path) as f:
        services_data = yaml.safe_load(f) or {}
    
    # Parse service selection
    selected_services = parse_services_input(services_input)
    selected_list = [s.strip() for s in selected_services.split(',') if s.strip()]
    
    # Build output
    lines = []
    lines.append('# Auto-generated Docker bake file')
    lines.append('# Generated from services.yaml + config.yaml - DO NOT EDIT MANUALLY')
    lines.append('')
    lines.append(f'# Source config: {config_path}')
    lines.append(f'# Source services: {services_def_path}')
    lines.append('')
    
    # Common variables
    lines.append('variable "REGISTRY" { default = "' + registry + '" }')
    lines.append('variable "USERNAME" { default = "' + username + '" }')
    lines.append('variable "GIT_SHA" { default = "' + git_sha + '" }')
    lines.append('variable "GIT_BRANCH" { default = "' + git_branch + '" }')
    lines.append('variable "REPO_SUFFIX" { default = "' + repo_suffix + '" }')
    lines.append('')
    
    # Track targets
    all_targets = []
    python_targets = []
    
    # Process each service
    for service_name in selected_list:
        service_spec = services_data.get('services', {}).get(service_name)
        if not service_spec:
            print(f"ERROR: Service '{service_name}' not found", file=sys.stderr)
            sys.exit(1)
        
        dockerfile = service_spec.get('dockerfile')
        image = service_spec.get('image')
        is_python = service_spec.get('is_python', False)
        
        all_targets.append(image)
        if is_python:
            python_targets.append(image)
        
        # Build args
        args_block = []
        args_spec = service_spec.get('args', {})
        
        for arg_name, arg_spec in args_spec.items():
            result = resolve_arg_value(arg_spec, config_data, host_rewrite)
            if isinstance(result, tuple):
                value, error = result
            else:
                value = result
                error = None
            if error:
                print(f"ERROR: {error} for '{arg_name}' in {config_path}", file=sys.stderr)
                sys.exit(1)
            args_block.append(f'        {arg_name} = "{value}"')
        
        # Output target
        lines.append(f'target "{image}" {{')
        lines.append('    context = "."')
        lines.append(f'    dockerfile = "{dockerfile}"')
        lines.append('    args = {')
        lines.extend(args_block)
        lines.append('    }')
        lines.append('    tags = [')
        lines.append(f'        "${{REGISTRY}}/${{USERNAME}}/{image}${{REPO_SUFFIX}}:latest",')
        lines.append(f'        "${{REGISTRY}}/${{USERNAME}}/{image}${{REPO_SUFFIX}}:${{GIT_SHA}}"')
        lines.append('    ]')
        lines.append('    platforms = ["linux/amd64"]')
        lines.append('    push = true')
        lines.append('    cache-from = ["type=gha"]')
        lines.append('    cache-to = ["type=gha,mode=max"]')
        lines.append('}')
        lines.append('')
    
    # Aggregate groups
    if all_targets:
        targets_str = ','.join(f'"{t}"' for t in all_targets)
        lines.append('# Aggregate group for all services')
        lines.append(f'group "all" {{ targets = [{targets_str}] }}')
        lines.append('')
    
    if python_targets:
        targets_str = ','.join(f'"{t}"' for t in python_targets)
        lines.append('# Aggregate group for Python services')
        lines.append(f'group "all-python" {{ targets = [{targets_str}] }}')
        lines.append('')
    
    # Write HCL output to file (summary goes to stdout)
    with open(output_file, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    
    # Print summary to stdout
    print(f'Generated {output_file}')
    print(f'  Config: {config_path}')
    print(f'  Services: {services_input} ({selected_services})')
    print(f'  Environment: {sys.argv[11] if len(sys.argv) > 11 else "dev"}')
    print(f'  Targets: {", ".join(all_targets)}')

if __name__ == '__main__':
    generate_bake()
PYEOF

chmod +x "$GENERATE_PY"

# Run the Python generator
python3 "$GENERATE_PY" \
    "$CONFIG_PATH" \
    "$SERVICES_DEF" \
    "$SERVICES_INPUT" \
    "$OUTPUT_FILE" \
    "$GIT_SHA" \
    "$GIT_BRANCH" \
    "$REGISTRY" \
    "$USERNAME" \
    "$REPO_SUFFIX" \
    "$HOST_REWRITE" \
    "$ENVIRONMENT"

# Cleanup temp file
rm -f "$GENERATE_PY"
