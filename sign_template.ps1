# sign_template.ps1
# Usage:
#   1) Edit $CertSubject OR $PfxPath/$PfxPassword below
#   2) Run AFTER building with PyInstaller
#   3) Adjust $DistExe if your exe name/version changes

$DistExe = ".\dist\XPadToggle-1.0.2\XPadToggle-1.0.2.exe"

# --- Option A: Use installed cert by Subject Name ---
$CertSubject = "CN=Ryan Frost"   # <-- change this to your cert's subject
$Timestamp = "http://timestamp.digicert.com"
signtool sign /fd SHA256 /tr $Timestamp /td SHA256 /n $CertSubject $DistExe

# --- Option B: Use a PFX file ---
# $PfxPath = "C:\path\to\codesign.pfx"
# $PfxPassword = "pfxPassword"
# $Timestamp = "http://timestamp.digicert.com"
# signtool sign /fd SHA256 /tr $Timestamp /td SHA256 /f $PfxPath /p $PfxPassword $DistExe

# Verify signature
signtool verify /pa /v $DistExe
