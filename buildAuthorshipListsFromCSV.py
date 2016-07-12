import unicodecsv as csv
import networkx as nx
import collections
import re
from io import BytesIO

# GROUPS OF SETTINGS FOR DIFFERENT ANALYSIS #




'''
# 1. inter-institutional... Oxford and Cambridge
#filenames
pubsFile = 'Publications_oxford-cambridge-CRUK_2011-03_2016.txt'
pubsFileClean = 'Publications_oxford-cambridge-CRUK_2011-03_2016-clean.txt'
# organise outputs by institution and include institution in outputs
crossInstitution = 1
# only show inter-institutional collaborations/coAuthorships
crossInstitutionOnly = 0
# whether to include edge/node meta data or not
includeEdgeData = 1
# if undirected, then only show each collaboration once, regardless of who reported it
undirectedGraph = 1
defaultInstitution = 'Oxford'
filePrefix = "ox-cam"

'''
# 2. Oxford only
#filenames
pubsFile = 'Publications_Simple_From20110101_To20160711_CancerCentre_20160711.csv'
pubsFileClean = 'Publications_Simple_From20110101_To20160711_CancerCentre_20160711-clean.csv'
# organise outputs by institution and include institution in outputs
crossInstitution = 0
# only show inter-institutional collaborations/coAuthorships
crossInstitutionOnly = 0
# whether to include edge/node meta data or not
includeEdgeData = 1
# if undirected, then only show each collaboration once, regardless of who reported it
undirectedGraph = 1
defaultInstitution = 'Oxford'
filePrefix = "ox-ox"




'''
# 3. Cambridge only
#filenames
pubsFile = 'Publications_cambridge-CRUK_2011-03_2016.txt'
pubsFileClean = 'Publications_cambridge-CRUK_2011-03_2016-clean.txt'
# organise outputs by institution and include institution in outputs
crossInstitution = 0
# only show inter-institutional collaborations/coAuthorships
crossInstitutionOnly = 0
# whether to include edge/node meta data or not
includeEdgeData = 1
# if undirected, then only show each collaboration once, regardless of who reported it
undirectedGraph = 1
defaultInstitution = 'Cambridge'
filePrefix = "cam-cam"
'''
# END OF SETTINGS #


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

with open(pubsFile,"rU") as infile, open(pubsFileClean,"wb") as outfile:
    c = infile.read()
    #c = infile.read().decode('utf-16le').encode('utf-8')
    reader = csv.reader((line.replace('\0','') for line in BytesIO(c)), delimiter=',', quotechar='"')
    writer = csv.writer(outfile)
    for line in reader:
        writer.writerow([remove_quotes(elem) for elem in line])

###########################################################################################################
# At this point, we'll have cleaned output files, encoded in a manageable format
###########################################################################################################

counts = {'pubsource':0,'edges':0,'edgesgraph':0,'nodes':0,'nodesgraph':0}

with open(pubsFileClean, 'rb') as csvfile:
    reader = csv.reader((line.replace('\0','') for line in csvfile), delimiter=',', quotechar='"')

    pubMarkers = ['Proprietary ID', 'DOI', 'Author URL', 'ID']
    publications = {}
    keyWords = {'Oxford': [], 'Cambridge': []}
    authorColumns = []
    authors = {}

    # initialise dictionary to store all publication references
    for variable in pubMarkers:
        publications[variable] = {}

    isHeader = 1
    # loop through all entries in the source publication file to create publication
    #   records organised by as many unique identifiers as the data contains
    for row in reader:
        if isHeader:
            isHeader = 0
            authorColumns = row
            authorColumns[0] = 'ID'
        else:
            counts['pubsource']+=1
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
                if(variable in newRecord and len(newRecord[variable])):
                    # if first encounter of this publication, initialise variables
                    if(newRecord[variable] not in publications[variable]):
                        publications[variable][newRecord[variable]] = {'authorIDs': [], 'authorInsts': [], 'coauthors': [], 'keywords': [], 'title': '', 'type': '', 'publicationName': ''}
                    # record authors, either with or without
                    publications[variable][newRecord[variable]]['authorIDs'].append(newRecord['Username'])
                    if crossInstitution and 'Institution' in newRecord:
                        publications[variable][newRecord[variable]]['authorInsts'].append(newRecord['Institution'])
                    else:
                        publications[variable][newRecord[variable]]['authorInsts'].append(defaultInstitution)
                    # record the longest list of authors available
                    if(len(re.split(', |; |,|;', newRecord['Authors'])) > len(publications[variable][newRecord[variable]]['coauthors'])):
                        publications[variable][newRecord[variable]]['coauthors'] = re.split(', |; |,|;', newRecord['Authors'])
                    # record unique key word values
                    for word in re.split(', |; |,|;', newRecord['Keywords']):
                        if len(word.strip()) and word.strip() not in publications[variable][newRecord[variable]]['keywords']:
                            publications[variable][newRecord[variable]]['keywords'].append(word.strip())
                            if crossInstitution and 'Institution' in newRecord:
                                keyWords[newRecord['Institution']].append(word.strip())
                            else:
                                keyWords[defaultInstitution].append(word.strip())
                    # record title
                    publications[variable][newRecord[variable]]['title'] = newRecord['Title']
                    # record publication type
                    publications[variable][newRecord[variable]]['type'] = newRecord['Publication type']
                    # record journal name
                    publications[variable][newRecord[variable]]['publicationName'] = newRecord['Journal OR Proceedings']
                    if len(newRecord['Canonical journal title']):
                        publications[variable][newRecord[variable]]['publicationName'] = newRecord['Canonical journal title']
                    # add date if available
                    publications[variable][newRecord[variable]]['publicationDate'] = newRecord['Reporting date 1']
                    # add marker values for comparisons of duplicates below
                    for compareVar in pubMarkers:
                        if compareVar in newRecord:
                            publications[variable][newRecord[variable]][compareVar] = newRecord[compareVar]

            # store author/node data
            if 'Username' in newRecord and newRecord['Username'] not in authors:
                authors[newRecord['Username']] = {
                                                'name': newRecord['Name'],
                                                'institution': newRecord['Institution'] if 'Institution' in newRecord else defaultInstitution,
                                                'cross-institution': -1,
                                                'department': newRecord['Primary group'],
                                                }
                counts['nodes']+=1

###########################################################################################################
# At this point, we have a dictionary of publication records indexed by all possible identifying markers
###########################################################################################################


    # initiate graph
    authG = nx.Graph()

    # open output csv file
    with open(filePrefix+"-edges.csv", "wb") as f:
        writer = csv.writer(f)
        # create list of all found co-authorship records
        coAuthorships = {}
        compareType = ['ID']
        includedAuthors = {}
        foundPubs = {}
        # if cross-institution, compare external IDs to determine links
        if crossInstitution:
            compareType = ['Proprietary ID', 'DOI']
        # loop through each dictionary sorted by publication unique identifier and extract coAuthorship pairings
        for thisType in compareType:
            # loop through all publications of the current compare type
            for pub in publications[thisType]:
                # if more than one known authors is listed as an author, identify flag as a collaboration(s)
                if len(publications[thisType][pub]['authorIDs']) > 1:
                    # loop through all possible pairings of all identified authors
                    for pairing in combinantorial(publications[thisType][pub]['authorIDs']):
                        coAuthorshipIncluded = 0
                        # ensure all possible pairings of two individuals are considered in the same way (alphabetical)
                        pairing = sorted(pairing)
                        # create index-friendly tuple of pairing
                        thisPair = tuple(sorted(pairing))
                        # check if pairing is already accounted for with this publication
                        if thisPair in coAuthorships and publications[thisType][pub][thisType] in coAuthorships[thisPair]:
                            print "record already found: "+pub
                            break
                        # if within one institution, consider each pairing a collaboration
                        if not crossInstitution:
                            coAuthorshipIncluded = 1
                        else:
                            # flag to set authors as cross institution or not
                            authorsCrossInstitution = 0
                            # if only interested in cross institution edges, ensure both institutions are represented
                            insts = [publications[thisType][pub]['authorInsts'][publications[thisType][pub]['authorIDs'].index(pairing[0])], publications[thisType][pub]['authorInsts'][publications[thisType][pub]['authorIDs'].index(pairing[1])]]
                            if insts[0] is not insts[1]:
                                authorsCrossInstitution = 1
                            if(not crossInstitutionOnly or authorsCrossInstitution):
                                if authorsCrossInstitution:
                                    authors[pairing[0]]['cross-institution'] = 1
                                    authors[pairing[1]]['cross-institution'] = 1
                                else:
                                    if authors[pairing[0]]['cross-institution'] == -1:
                                        authors[pairing[0]]['cross-institution'] = 0
                                    if authors[pairing[1]]['cross-institution'] == -1:
                                        authors[pairing[1]]['cross-institution'] = 0
                                coAuthorshipIncluded = 1
                        # if found, add edge data for selected coAuthorship
                        if coAuthorshipIncluded:
                            # if not already present, create record for co-authorship
                            if thisPair not in coAuthorships:
                                coAuthorships[thisPair] = {}
                                counts['edges']+=1
                            # add a marker for each publication identifier for this collaboration
                            for knownType in compareType:
                                coAuthorships[thisPair][publications[thisType][pub][knownType]] = {'duplicate': 1, 'weight': 0}
                            includedAuthors[pairing[0]] = authors[pairing[0]]
                            includedAuthors[pairing[1]] = authors[pairing[1]]
                            # calculate weight of edge
                            authCount = len(publications[thisType][pub]['coauthors'])
                            if authCount > 1:
                                calcWeight = 1/float(authCount-1)
                            else:
                                calcWeight = 1

                            # add edge data
                            coAuthorships[thisPair][publications[thisType][pub][thisType]] = {
                                                        'duplicate': 0,
                                                        'weight': calcWeight,
                                                        'type': publications[thisType][pub]['type'],
                                                        'title': publications[thisType][pub]['title'],
                                                        'publicationName': publications[thisType][pub]['publicationName'],
                                                        'publicationDate': publications[thisType][pub]['publicationDate'],
                                                        'coauthors': publications[thisType][pub]['coauthors'],
                                                        'keywords': publications[thisType][pub]['keywords']
                                                    }

                            # add weighted pairing to network graph
                            if pairing[0] not in authG:
                                authG.add_node(pairing[0])
                                counts['nodesgraph']+=1
                            if pairing[1] not in authG:
                                authG.add_node(pairing[1])
                                counts['nodesgraph']+=1
                            if not authG.has_edge(pairing[0], pairing[1]):
                                authG.add_edge(pairing[0], pairing[1], weight=calcWeight)
                                counts['edgesgraph']+=1
                            else:
                                authG[pairing[0]][pairing[1]]['weight'] += calcWeight

###########################################################################################################
# At this point, we have two lists representing coauthorship links (coAuthorships) and corresponding publication data (coAuthorshipData)
###########################################################################################################

        # write header line for output file
        header = ['Source', 'Target']
        if includeEdgeData:
            header.append('Collaborations')
            header.append('Weight')
            header.append('Publication Type')
            header.append('Publication Name')
            header.append('Publication Date')
            header.append('Title')
            header.append('Co-authors')
            header.append('Keywords')
        writer.writerow(header)

        # if more than one compare type is used, duplicate pairings are removed above (if undesired)
        # loop through each unique pairing and write it to the output file
        for coAuthors in coAuthorships:
            collabRow = list(coAuthors)
            # if desired, add edge data to csv output
            if includeEdgeData:
                currentCollabs = collections.OrderedDict([('weight', []), ('type', []), ('publicationName', []), ('publicationDate', []), ('title', []), ('coauthors', []), ('keywords', [])])
                for key in coAuthorships[coAuthors]:
                    if coAuthorships[coAuthors][key]['duplicate'] == 0 and coAuthorships[coAuthors][key]['weight'] > 0:
                        for var in currentCollabs:
                            if isinstance(coAuthorships[coAuthors][key][var], list):
                                currentCollabs[var].append(",".join(coAuthorships[coAuthors][key][var]))
                            else:
                                currentCollabs[var].append(coAuthorships[coAuthors][key][var])
                # add count as number of collaborations
                collabRow.append(len(currentCollabs['weight']))
                # add remaining compiled columns as a list of all values for each column
                for var in currentCollabs:
                    if isinstance(currentCollabs[var][0], int) or isinstance(currentCollabs[var][0], float):
                        if var is 'weight':
                            totalWeight = 0.0
                            for value in currentCollabs[var]:
                                totalWeight += float(value)
                            collabRow.append(totalWeight)
                        else:
                            collabRow.append('|'.join(map(str, currentCollabs[var])))
                    else:
                        collabRow.append(u'|'.join(currentCollabs[var]))
            writer.writerow(collabRow)

        # run centrality metrics on compiled graph
        closeness = nx.closeness_centrality(authG)
        betweenness = nx.betweenness_centrality(authG)
        #eigenvector = nx.eigenvector_centrality_numpy(authG, 'weight')
        pagerank = nx.pagerank_numpy(authG,0.85)

        departments = []
        with open(filePrefix+"-nodes.csv", "wb") as f2:
            nodeWriter = csv.writer(f2)
            # write header for nodes file
            nodeWriter.writerow(['ID', 'Name', 'Institution', 'Cross-institution', 'Department', 'Degree', 'Closeness', 'Betweenness', 'Pagerank'])
            # loop through all included nodes
            for key, value in includedAuthors.iteritems():
                nodeWriter.writerow([key, value['name'].title(), value['institution'], value['cross-institution'], value['department'], authG.degree(key), closeness[key], betweenness[key], pagerank[key]])
                departments.append(value['institution']+":"+value['department'])

        with open(filePrefix+"-keywords.csv", "wb") as f2:
            nodeWriter = csv.writer(f2)
            # write header for nodes file
            nodeWriter.writerow(['Institution', 'Word', 'Count'])
            # loop through all included nodes
            for inst, wordList in keyWords.iteritems():
                for word in collections.Counter(wordList).most_common(250):
                    nodeWriter.writerow([inst, word[0], word[1]])

        with open(filePrefix+"-departments.csv", "wb") as f2:
            nodeWriter = csv.writer(f2)
            # write header for nodes file
            nodeWriter.writerow(['Institution', 'Department'])
            # loop through all included nodes
            for dept in collections.Counter(departments).most_common():
                nodeWriter.writerow(dept)

###########################################################################################################
# At this point, we have output files for all data reports required
###########################################################################################################

print "Edge, keyword, dept & node file complete"

print counts
print nx.number_of_nodes(authG)
print nx.number_of_edges(authG)
print nx.is_directed(authG)
print nx.info(authG)
