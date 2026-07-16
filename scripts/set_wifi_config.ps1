<#
.SYNOPSIS
    Configure the ClickShare Base Unit's WiFi Access Point (SSID, channel, band)
    via the v3 REST API.

.DESCRIPTION
    The REST API's /v3/login/internal endpoint issues a short-lived (1 minute)
    session via a real Set-Cookie: client-session=<jwt> response header (it is
    NOT just the JSON body value used verbatim - see rest-api-apk
    AuthModule.kt/AuthRouting.kt). Because the apikey is single-use / expires
    quickly, a fresh login is performed immediately before each REST call
    (GET and PATCH).

    This script relies on PowerShell's WebRequestSession (-SessionVariable /
    -WebSession) to capture and resend that cookie automatically, since
    Invoke-WebRequest/Invoke-RestMethod strip the raw Set-Cookie header out of
    the visible response Headers collection once it's consumed into the
    session's cookie container.

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
$loginHeaders = @{ "accept" = "application/json"; "Sec-Fetch-Site" = "same-origin" }

function Invoke-RestWithDiagnostics {
    param([string]$Uri, [string]$Method, [hashtable]$Headers, [string]$Body, [Microsoft.PowerShell.Commands.WebRequestSession]$Session)
    try {
        if ($Body) {
            return Invoke-RestMethod -Uri $Uri -Method $Method -Headers $Headers -ContentType "application/json" -Body $Body -WebSession $Session
        }
        return Invoke-RestMethod -Uri $Uri -Method $Method -Headers $Headers -WebSession $Session
    } catch {
        $respBody = $null
        if ($_.Exception.Response) {
            try {
                $stream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($stream)
                $respBody = $reader.ReadToEnd()
            } catch { }
        }
        Write-Host "Request to $Uri failed: $($_.Exception.Message)"
        if ($respBody) { Write-Host "Response body: $respBody" }
        throw
    }
}

Write-Host "Logging in (for GET)..."
Invoke-RestMethod -Uri "$baseUrl/v3/login/internal" -Method Post -Headers $loginHeaders -ContentType "application/json" -Body "" -SessionVariable webSession | Out-Null

Write-Host "Reading current wireless config from $baseUrl/v3/network/wireless/1 ..."
$current = Invoke-RestWithDiagnostics -Uri "$baseUrl/v3/network/wireless/1" -Method "Get" -Headers $loginHeaders -Session $webSession

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

Write-Host "Logging in again (for PATCH, apikey is single-use)..."
Invoke-RestMethod -Uri "$baseUrl/v3/login/internal" -Method Post -Headers $loginHeaders -ContentType "application/json" -Body "" -WebSession $webSession | Out-Null

Write-Host "Applying wireless config..."
$patchHeaders = @{ "accept" = "*/*"; "Sec-Fetch-Site" = "same-origin" }
$result = Invoke-RestWithDiagnostics -Uri "$baseUrl/v3/network/wireless/1" -Method "Patch" -Headers $patchHeaders -Body $bodyJson -Session $webSession
Write-Host "Done:"
$result | ConvertTo-Json -Depth 10
