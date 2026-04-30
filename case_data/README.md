# Case Data Directory

Place forensic artifacts in this directory for analysis by Find Evil!.

## Directory Structure

```
case_data/
├── disk_image.dd           # Disk image (E01, DD, or similar)
├── memory_dump.dmp         # Memory dump (DMP or similar)
├── evtx/                   # Windows Event Log files
│   ├── Security.evtx
│   ├── System.evtx
│   └── Application.evtx
├── registry/               # Registry hive files
│   ├── SAM
│   ├── SYSTEM
│   ├── SOFTWARE
│   └── SECURITY
└── README.md              # Case notes
```

## Supported Artifacts

### Disk Images
- Raw (.dd, .raw)
- EnCase (.E01, .E02, etc.)
- Xen (.xen)
- VDI/VMDK (requires conversion)

### Memory Dumps
- Windows (.DMP)
- Volatility crash dumps
- Raw memory files

### Logs and Registry
- Windows Event Logs (.evtx)
- Registry hives (SAM, SYSTEM, SOFTWARE, SECURITY)
- Prefetch files (\Windows\Prefetch\*.pf)

## Usage

1. Copy case artifacts to this directory
2. Run: `python main.py --case-data ./case_data --image disk.dd --memory memory.dmp`
3. Reports will be generated in `./exports/`

## Notes

- All files are analyzed in read-only mode (no modifications)
- Sensitive data in reports should be sanitized before sharing
- Chain of custody is maintained in execution logs
