import unicodecsv as csv
import re
from io import BytesIO

pubsFile = 'Publications_oxford-cambridge-CRUK_2011-03_2016.txt'
#pubsFile = 'Publications_sample.txt'
pubsFileClean = 'Publications_oxford-cambridge-CRUK_2011-03_2016-clean.txt'

crossInstitution = 1
crossInstitutionOnly = 0
removeDuplicates = 0
includeEdgeData = 1

def remove_quotes(s):
    return ''.join(c for c in s if c not in ('"','\n','\r'))

def combinantorial(lst):
    count = 0
    index = 1
    pairs = []
    for element1 in lst:
        for element2 in lst[index:]:
            pairs.append((element1, element2))
        index += 1
    return pairs

with open(pubsFile,"rb") as infile, open(pubsFileClean,"wb") as outfile:
    c = infile.read().decode('utf-16le').encode('utf-8')
    reader = csv.reader((line.replace('\0','') for line in BytesIO(c)), delimiter='	', quotechar='"')
    writer = csv.writer(outfile)
    for line in reader:
        writer.writerow([remove_quotes(elem) for elem in line])

with open(pubsFileClean, 'rb') as csvfile:
    reader = csv.reader((line.replace('\0','') for line in csvfile), delimiter=',', quotechar='"')

    pubMarkers = ['Proprietary ID', 'DOI', 'Author URL', 'ID']
    publications = {}
    authorColumns = []
    authors = {}

    # initialise dictionary to store all publication references
    for variable in pubMarkers:
        publications[variable] = {}

    isHeader = 1
    # loop through all entries in the source publication file
    for row in reader:
        if isHeader:
            isHeader = 0
            authorColumns = row
            authorColumns[0] = 'ID'
        else:
            idx = 0
            newRecord = {}

            for idx, col in enumerate(row):
                newRecord[authorColumns[idx]] = col

            # add current author id to list of authors for current:
            #   'ProprietaryID',
            #   'DOI',
            #   'Author URL',
            #   'ID' (ID for inter Oxford connections only)
            for variable in pubMarkers:
                if(len(newRecord[variable])):
                    # if first encounter of this publication, initialise variables
                    if(newRecord[variable] not in publications[variable]):
                        publications[variable][newRecord[variable]] = {'authorIDs': [], 'coauthors': [], 'keywords': [], 'title': '', 'type': '', 'publicationName': ''}
                    # record authors, either with or without institution
                    if crossInstitution and 'Institution' in newRecord:
                        publications[variable][newRecord[variable]]['authorIDs'].append(newRecord['Institution']+'-'+newRecord['Username'])
                    else:
                        publications[variable][newRecord[variable]]['authorIDs'].append(newRecord['Username'])
                    # record the longest list of authors available
                    if(len(re.split(', |; |,|;', newRecord['Authors'])) > len(publications[variable][newRecord[variable]]['coauthors'])):
                        publications[variable][newRecord[variable]]['coauthors'] = re.split(', |; |,|;', newRecord['Authors'])
                    # record unique key word values
                    for word in re.split(', |; |,|;', newRecord['Keywords']):
                        if len(word.strip()) and word.strip() not in publications[variable][newRecord[variable]]['keywords']:
                            publications[variable][newRecord[variable]]['keywords'].append(word.strip())
                    # record title
                    publications[variable][newRecord[variable]]['title'] = newRecord['Title']
                    # record publication type
                    publications[variable][newRecord[variable]]['type'] = newRecord['Publication type']
                    # record journal name
                    publications[variable][newRecord[variable]]['publicationName'] = newRecord['Journal OR Proceedings']
                    if len(newRecord['Canonical journal title']):
                        publications[variable][newRecord[variable]]['publicationName'] = newRecord['Canonical journal title']

            # store author/node data
            if(newRecord['Username'] not in authors):
                authors[newRecord['Username']] = {
                                                'name': newRecord['Name'],
                                                'institution': newRecord['Institution'],
                                                'department': newRecord['Primary group'],
                                                }

    # open output csv file
    with open("author-edges.csv", "wb") as f:
        writer = csv.writer(f)
        # create list of all found co-authorship records
        coAuthorships = []
        coAuthorshipData = []
        compareType = ['ID']
        edgeList = {}
        # if cross-institution, compare external IDs to determine links
        if crossInstitution:
            compareType = ['Proprietary ID', 'DOI']
        # loop through each compare type
        for thisType in compareType:
            # loop through all publications of the current compare type
            for pub in publications[thisType]:
                # if more than one known authors is listed as an author, identify flag as a collaboration(s)
                if len(publications[thisType][pub]['authorIDs']) > 1:
                    # loop through all possible pairings of all identified authors
                    for pairing in combinantorial(publications[thisType][pub]['authorIDs']):
                        coAuthorshipIncluded = 0
                        thisPair = pairing
                        # if within one institution, consider each pairing a collaboration
                        if not crossInstitution:
                            if not removeDuplicates or pairing not in coAuthorships:
                                coAuthorships.append(pairing)
                                coAuthorshipIncluded = 1
                        else:
                            # if only interested in cross institution edges, ensure both institutions are represented
                            insts = [pairing[0].split('-')[0], pairing[1].split('-')[0]]
                            # TODO: remove hard coded institution references
                            if(not crossInstitutionOnly or ('Oxford' in insts and 'Cambridge' in insts)):
                                thisPair = [pairing[0].split('-')[1], pairing[1].split('-')[1]]
                                if not removeDuplicates or thisPair not in coAuthorships:
                                    coAuthorships.append(thisPair)
                                    coAuthorshipIncluded = 1
                        # if found, add edge data for selected coAuthorship
                        if coAuthorshipIncluded:
                            edgeList[thisPair[0]] = authors[thisPair[0]]
                            edgeList[thisPair[1]] = authors[thisPair[1]]
                            if includeEdgeData:
                                coAuthorshipData.append({
                                                        'type': publications[thisType][pub]['type'],
                                                        'title': publications[thisType][pub]['title'],
                                                        'publicationName': publications[thisType][pub]['publicationName'],
                                                        'coauthors': publications[thisType][pub]['coauthors'],
                                                        'keywords': publications[thisType][pub]['keywords']
                                                    })


        # write header line for output file
        header = ['Collaborator1', 'Collaborator2']
        if includeEdgeData:
            header.append('Type')
            header.append('Publication Name')
            header.append('Title')
            header.append('Co-authors')
            header.append('Keywords')
        writer.writerow(header)

        # if more than one compare type is used, duplicate pairings are removed above
        # loop through each unique pairing and write it to the output file
        for idx, coAuthors in enumerate(coAuthorships):
            # if desired, add edge data to csv output
            if includeEdgeData:
                coAuthors.append(coAuthorshipData[idx]['type'])
                coAuthors.append(coAuthorshipData[idx]['publicationName'])
                coAuthors.append(coAuthorshipData[idx]['title'])
                coAuthors.append(", ".join(coAuthorshipData[idx]['coauthors']))
                coAuthors.append(", ".join(coAuthorshipData[idx]['keywords']))
            writer.writerow(coAuthors)

        with open("author-nodes.csv", "wb") as f2:
            nodeWriter = csv.writer(f2)
            # write header for nodes file
            nodeWriter.writerow(['ID', 'Name', 'Institution', 'Department'])
            # loop through all included nodes
            for key, value in edgeList.iteritems():
                nodeWriter.writerow([key, value['name'], value['institution'], value['department']])


print "Edge & node file complete"
