# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Performs post-creation configuration on a visual remote desktop.
# This is the Windows PowerShell equivalent of the Linux startup script:
# remotedesktopconfigure.py
# Both script are functionally equivalent and should be kept in sync
# as much as possible considering platform differences.

#
# Utils
#

function Get-Metadata {
  <#
  .SYNOPSIS
    Get value from instance metadata.
  .PARAMETER Key
    Key path.
  .PARAMETER Default
    Default value if key is not in metadata.
  .EXAMPLES
    Get-Metadata 'attributes/nvidia_driver_version'
    Get-Metadata 'attributes/nvidia_driver_version' '430.63'
    Get-Metadata -Key 'id'
    Get-Metadata -Key 'name' -Default 'instance1'
  #>
  param (
    [parameter(Mandatory=$true, Position=1)]
    [String]$Key,

    [parameter(Mandatory=$false, Position=2)]
    [String]$Default
  )

  $Headers = @{'Metadata-Flavor' = 'Google'}
  $BaseUri = 'http://metadata.google.internal/computeMetadata/v1/instance/'
  $Uri = "${BaseUri}/${Key}?alt=text"
  try {
    $Value = Invoke-RestMethod -Headers $Headers -Uri $Uri
    return $Value
  } catch [System.Net.WebException] {
    if ($_.Exception.Response.StatusCode.value__ -eq 404 -and
        $PSBoundParameters.ContainsKey('Default')) {
      return $Default
    }
    else {
      throw
    }
  }
}


#
# Configuration steps
#

function Configure-Teradici {
  <#
  .SYNOPSIS
    Registers PCoIP Agent.
  #>
  Write-Host 'Configuring: Teradici'

  Write-Host 'Registering PCoIP Agent'

  & 'C:\Program Files\Teradici\PCoIP Agent\pcoip-validate-license.ps1'
  if ($LastExitCode -eq 0) {
    Write-Host 'PCoIP is already registered.'
    return
  }

  $Code = Get-Metadata 'attributes/teradici_registration_code'
  & 'C:\Program Files\Teradici\PCoIP Agent\pcoip-register-host.ps1' -Verbose -RegistrationCode $Code
}


#
# Bootstrap
#

Configure-Teradici
