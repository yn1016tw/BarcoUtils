<#
.SYNOPSIS
    Configure the ClickShare Base Unit's WiFi Access Point (SSID, channel, band)
    via the v3 REST API.

.DESCRIPTION
    The v3 REST API requires a fresh one-time API key for every call:
        1. POST /v3/login/internal  -> returns an apikey
        2. Send it back as Cookie: client-session=<apikey> on the next call
    A new login is performed before each REST call (GET and PATCH), as the
    apikey is single-use.

.PARAMETER DeviceIp
    IP address of the ClickShare Base Unit.

.PARAMETER RestPort
    REST API port (default 4003).

.PARAMETER Ssid
    SSID to configure on the Access Point (e.g. "Clickshare-9752000162").

.PARAMETER Channel
    WiFi channel to configure (default 7).

.PARAMETER FrequencyBand
    Frequency band to configure (default "2.4 GHz").

.PARAMETER OperationMode
    Wireless operation mode (default "AccessPoint").
#>
param(
    [Parameter(Mandatory = $true)][string]$DeviceIp,
    [int]$RestPort = 4003,
    [Parameter(Mandatory = $true)][string]$Ssid,
    [int]$Channel = 7,
    [string]$FrequencyBand = "2.4 GHz",
    [string]$OperationMode = "AccessPoint"
)

$ErrorActionPreference = "Stop"

# Allow self-signed certificates (device uses a local HTTPS cert)
if (-not ("TrustAllCertsPolicy" -as [type])) {
    Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
}
"@
}
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

$baseUrl = "https://${DeviceIp}:${RestPort}"

function Get-ApiKey {
    $resp = Invoke-RestMethod -Uri "$baseUrl/v3/login/internal" -Method Post -Headers @{ "accept" = "application/json"; "Sec-Fetch-Site" = "same-origin" } -ContentType "application/json" -Body ""
    $key = $resp.apikey
    if (-not $key) { $key = $resp.apiKey }
    if (-not $key) { $key = $resp.token }
    if (-not $key) { throw "Could not find apikey in /login/internal response: $($resp | ConvertTo-Json -Compress)" }
    return $key
}

Write-Host "Logging in to get apikey (for GET)..."
$apikey1 = Get-ApiKey
$headers1 = @{ "Cookie" = "client-session=$apikey1"; "Sec-Fetch-Site" = "same-origin" }

Write-Host "Reading current wireless config from $baseUrl/v3/network/wireless/1 ..."
$current = Invoke-RestMethod -Uri "$baseUrl/v3/network/wireless/1" -Method Get -Headers $headers1

$current.operationMode = $OperationMode
if (-not $current.accessPoint) {
    $current | Add-Member -MemberType NoteProperty -Name accessPoint -Value ([pscustomobject]@{})
}
$current.accessPoint.ssid = $Ssid
$current.accessPoint.channel = $Channel
$current.accessPoint.frequencyBand = $FrequencyBand

$bodyJson = $current | ConvertTo-Json -Depth 10
Write-Host "New config:"
Write-Host $bodyJson

Write-Host "Logging in to get apikey (for PATCH)..."
$apikey2 = Get-ApiKey
$headers2 = @{ "Cookie" = "client-session=$apikey2"; "Sec-Fetch-Site" = "same-origin" }

Write-Host "Applying wireless config..."
$result = Invoke-RestMethod -Uri "$baseUrl/v3/network/wireless/1" -Method Patch -Headers $headers2 -ContentType "application/json" -Body $bodyJson
Write-Host "Done:"
$result | ConvertTo-Json -Depth 10
