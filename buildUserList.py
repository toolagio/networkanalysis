import urllib2
import csv
from lxml import etree

host = 'https://oxris.ox.ac.uk:8091/elements-api/v4.9/users?detail=full'
apiNSValue = 'http://www.symplectic.co.uk/publications/api'
apiNamespace = {'api': apiNSValue}
#host = 'https://oxris-qa.bsp.ox.ac.uk:8091/elements-api/v4.9/users'
user= 'symplecticONCOLOGYVIVO'
passwd = 'SymplecticOn1'

usersFile = 'users.csv'

passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
# this creates a password manager
passman.add_password(None, host, user, passwd)
# because we have put None at the start it will always
# use this username/password combination for  urls
# for which `theurl` is a super-url

authhandler = urllib2.HTTPBasicAuthHandler(passman)
# create the AuthHandler

opener = urllib2.build_opener(authhandler)

urllib2.install_opener(opener)
# All calls to urllib2.urlopen will now use our handler
# Make sure not to include the protocol in with the URL, or
# HTTPPasswordMgrWithDefaultRealm will be very confused.
# You must (of course) use it when fetching the page though.

# pagehandle = urllib2.urlopen(host)
# authentication is now handled automatically for us

nextPageURL = host;
with open(usersFile, 'wb') as csvfile:
    csvWriter = csv.writer(csvfile, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)

    while (nextPageURL != ''):
        xmlString = ''
        # make API call
        response = urllib2.urlopen(nextPageURL)
        xmlParsed = etree.parse(response)

        users = []
        # parse the required data from the response xml
        for userXml in xmlParsed.xpath("//api:object[@category='user']/..", namespaces=apiNamespace):
            titleElement = userXml.find("{http://www.w3.org/2005/Atom}title")
            objectElement = userXml.find("{"+apiNSValue+"}object")
            lastName = titleElement.text.split(",")[0].strip()
            firstName = ""
            if(len(titleElement.text.split(",")) > 1):
                firstName = titleElement.text.split(",")[1].strip()
            users.append({
                'ID': unicode(objectElement.get('id').strip()) if ('id' in objectElement.attrib) else '',
                'Username': unicode(objectElement.get('username').strip()) if ('username' in objectElement.attrib) else '',
                'ProprietaryID': unicode(objectElement.get('proprietary-id').strip()) if ('proprietary-id' in objectElement.attrib) else '',
                'FirstName': unicode(firstName.strip()),
                'LastName': unicode(lastName.strip())
            })

        # write the data to the CSV file
        for user in users:
            csvWriter.writerow([user[s].encode("utf-8") for s in user])

        # extract next page of results, if present
        nextPageElement = xmlParsed.xpath(".//api:pagination/api:page[@position='next']", namespaces=apiNamespace)
        nextPageURL = '';
        if len(nextPageElement):
            nextPageURL = nextPageElement[0].attrib["href"]

print "User file complete"
