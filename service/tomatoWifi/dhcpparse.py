def addDhcpData(rows):
    """given dicts with 'mac', add other data from the dhcp cache"""
    currentLease = None
    for line in open('/var/lib/dhcp/dhcpd.leases'):
        if line.startswith('lease '):
            currentLease = {'ip': line.split()[1]}
        elif line.startswith('  hardware ethernet '):
            currentLease['mac'] = line.split()[2].strip(';').upper()
        elif line.startswith('  client-hostname'):
            currentLease['clientHostname'] = line.split(None, 2)[1].strip('";')
        elif line.startswith('  binding state'):
            currentLease['bindingState'] = line.split()[2].strip(';')
        elif line.startswith('}'):
            if currentLease.get('bindingState') == 'active':
                # there seem to be a lot of 'active' blocks
                # for the same ip addr and mac. I haven't
                # looked into whether they hold different
                # lease terms or what
                for r in rows:
                    if r['mac'] == currentLease['mac']:
                        r.update(currentLease)
                        
            
