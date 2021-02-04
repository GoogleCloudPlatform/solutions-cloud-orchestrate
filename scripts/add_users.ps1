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
#
# Import active directory module for running AD cmdlets
Import-Module activedirectory

# Define domain for UserPrincipalName.
$Domain = mydomain.com
  
# Store the data from users.csv in the $ADUsers variable.
$ADUsers = Import-csv C:\users.csv

# Loop through each row in the CSV file.
foreach ($User in $ADUsers)
{

  # Read user data from each field in each row and assign the data to a
  # variable as below.
	$Username 	   = $User.username
	$Password 	   = $User.password
	$Firstname 	   = $User.firstname
	$Lastname 	   = $User.lastname
	$OU 		       = $User.ou
  $email         = $User.email
  $streetaddress = $User.streetaddress
  $city          = $User.city
  $zipcode       = $User.zipcode
  $state         = $User.state
  $country       = $User.country
  $telephone     = $User.telephone
  $jobtitle      = $User.jobtitle
  $company       = $User.company
  $department    = $User.department
  $Password      = $User.Password

	# Check to see if the user already exists in AD.
	if (Get-ADUser -F {SamAccountName -eq $Username})
	{
		 # If user already exists, skip.
		 Write-Warning "A user account with username $Username already exist in Active Directory."
	}
	else
	{
		# Create the new user.
    Write "Creating user $Username..."
		New-ADUser `
            -SamAccountName $Username `
            -UserPrincipalName "$Username@$Domain" `
            -Name "$Firstname $Lastname" `
            -GivenName $Firstname `
            -Surname $Lastname `
            -Enabled $True `
            -DisplayName "$Lastname, $Firstname" `
            -Path $OU `
            -City $city `
            -Company $company `
            -State $state `
            -StreetAddress $streetaddress `
            -OfficePhone $telephone `
            -EmailAddress $email `
            -Title $jobtitle `
            -Department $department `
            -AccountPassword (convertto-securestring $Password -AsPlainText -Force) -ChangePasswordAtLogon $True
            
	} # end if
} # end foreach
