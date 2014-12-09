#
# USAGE:
#
# $> python run_msas.py P N
#
# P is the path to a fasta-formatted file with sequences to be aligned.
# N is the short nickname of the analysis.
#
from argParser import *
from tools import *
from asrpipelinedb import *
from log import *
from plots import *
from phyloasr import *

""""
The original shelll script....

mkdir MUSCLE
mkdir PRANK
mkdir MSAPROBS
cp cgmc.erg.raw.fasta cgmc.txt
python SCRIPTS/clean_seqs.py cgmc.txt > cgmc.fasta
mpirun -np 4 SCRIPTS/run_msas.mpi.sh
"""
from asrpipelinedb_api import *

def read_fasta(fpath):
    """Ignores redundant taxa."""
    fin = open(fpath, "r")    
    taxanames = []
    taxa_seq = {}
    last_taxa = None
    last_seq = ""
    okay = True
    for l in fin.xreadlines():
        l = l.strip()
        if l.__len__() <= 2:
            pass
        elif l.startswith(">"):
            okay = True
            taxaname = re.sub(">", "", l.split()[0] )
            if taxaname in taxa_seq:
                okay = False
            else:
                if last_taxa != None:
                    taxa_seq[last_taxa] = last_seq
                last_taxa = taxaname
                last_seq = ""
                
        elif okay == True:
            last_seq += l
    if last_taxa != None:
        taxa_seq[last_taxa] = last_seq
    
    fin.close()
    
    return taxa_seq

def import_and_clean_erg_seqs(con, ap):  
    """This method imports original sequences (unaligned) and builds entries
    in the SQL tables Taxa and OriginalSequences.
    Note: these tables are wiped clean before inserting new data."""  
    ergseqpath = get_setting_values(con, "ergseqpath")[0]

    taxa_seq = read_fasta(ergseqpath)

    cur = con.cursor()
    sql = "delete from OriginalSequences"
    cur.execute(sql)
    sql = "delete from Taxa"
    cur.execute(sql)
    con.commit()
    
    for taxon in taxa_seq:
        import_original_seq(con, taxon, taxa_seq[taxon] )
        print taxon, taxa_seq[taxon]
    
    cleanpath = get_setting_values(con, "ergseqpath")[0]
    fout = open(cleanpath, "w")
    for taxon in taxa_seq:
        fout.write(">" + taxon + "\n")
        fout.write(taxa_seq[taxon] + "\n")
    fout.close()
    
def verify_erg_seqs(con):
    """Sanity Check:"""
    cur = con.cursor()
    sql = "select count(*) from Taxa"
    cur.execute(sql)
    c = cur.fetchone()[0]
    write_log(con, "There are " + c.__str__() + " taxa in the database.")

    sql = "select count(*) from OriginalSequences"
    cur.execute(sql)
    c = cur.fetchone()[0]
    write_log(con, "There are " + c.__str__() + " sequences in the database.")
    
    """Is the seed sequence found?"""
    seeds = get_setting_values(con, "seedtaxa")
    for s in seeds:
        sql = "select count(*) from Taxa where shortname='" + s + "'"
        cur.execute(sql)
        x = cur.fetchone()[0]
        if x == 0:
            write_error(con, "I cannot find your seed taxa '" + s + "' in your original sequences.")
            exit()
        
    
def write_msa_commands(con, ap):
    cur = con.cursor()
    
    p = "SCRIPTS/msas.commands.sh"
    fout = open(p, "w")
    
    sql = "select id, name, exe_path from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        msaid = ii[0]
        msa = ii[1]
        exe = ii[2]
            
        if msa == "muscle":            
            fout.write(exe + " -maxhours 5 -in " + get_setting_values(con, "ergseqpath")[0] + " -out " + get_fastapath(msa) + "\n")
        elif msa == "prank":
            fout.write(exe + " -d=" + get_setting_values(con, "ergseqpath")[0] + " -o=" + get_fastapath(msa) + "\n")
        elif msa == "msaprobs": 
            fout.write(exe + " -num_threads 4 " + get_setting_values(con, "ergseqpath")[0] + " > " + get_fastapath(msa) + "\n")
        elif msa == "mafft": 
            fout.write(exe + " --thread 4 --auto " + get_setting_values(con, "ergseqpath")[0] + " > " + get_fastapath(msa) + "\n")
    fout.close()
    return p
    #os.system("mpirun -np 4 --machinefile hosts.txt /common/bin/mpi_dispatch SCRIPTS/msas.commands.sh")


def check_aligned_sequences(con, ap):
    cur = con.cursor()
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        msaid = ii[0]
        msa = ii[1]
        expected_fasta = get_fastapath(msa)
        if False == os.path.exists( expected_fasta ):
            write_error(con, "I can't find the expected FASTA output from " + msa + " at " + expected_fasta, code=None)
        taxa_seq = read_fasta(expected_fasta)
    
        """Does this alignment contain sequences?"""
        if taxa_seq.__len__() == 0:
            write_error(con, "I didn't find any sequences in the alignment from " + msa)
            
            sql = "delete from AlignmentMethods where id=" + msaid.__str__()
            cur.execute(sql)
            con.commit()
        
        """Clear any existing sequences, so that we can import fresh sequences."""
        sql = "delete from AlignedSequences where almethod=" + msaid.__str__()
        cur.execute(sql)
        con.commit()

        """Import each sequence in the alignment."""
        for taxa in taxa_seq:
            taxonid = get_taxonid(con, taxa)
            import_aligned_seq(con, taxonid, msaid, taxa_seq[taxa])
                 
        """Verify the importation occurred."""
        cur = con.cursor()
        sql = "select count(*) from AlignedSequences where almethod=" + msaid.__str__()
        cur.execute(sql)
        c = cur.fetchone()[0]
        write_log(con, "There are " + c.__str__() + " sequences in the " + msa + " alignment.")
     

def fasta_to_phylip(inpath, outpath):
    fin = open(inpath, "r")
    last_taxa = None
    taxa_seq = {}
    for l in fin.xreadlines():
        if l.startswith(">"):
            taxa = re.sub(">", "", l)
            taxa = taxa.split()[0] # trim any lingering GenBank labels. As of 03/2014, this line may be unecessary - split()[0] part of the parsing occurs when the RAW sequences are read into a FASTA file
            taxa = taxa.strip()
            last_taxa = taxa
            taxa_seq[ taxa ] = ""
        elif l.__len__() > 0:
            l = l.strip()
            taxa_seq[ last_taxa ] += l
    fin.close()
    
    fout = open(outpath, "w")
    fout.write("  " + taxa_seq.__len__().__str__() + "  " + taxa_seq[ taxa_seq.keys()[0] ].__len__().__str__() + "\n")
    for taxa in taxa_seq:
        fout.write(taxa + "   " + taxa_seq[taxa] + "\n")
    fout.close()

def convert_all_fasta_to_phylip(con):
    cur = con.cursor()
    for msa in get_alignment_method_names(con):
        f = get_fastapath(msa)
        p = get_phylippath(msa)
        fasta_to_phylip(f, p)
        f = get_trimmed_fastapath(msa)
        p = get_trimmed_phylippath(msa)
        fasta_to_phylip(f, p)
        f = get_raxml_fastapath(msa)
        p = get_raxml_phylippath(msa)
        fasta_to_phylip(f, p)
        
def bypass_zorro(con, ap):
    """Creates the post-zorro alignments, without running ZORRO and the resulting analysis."""
    for msa in get_alignment_method_names(con):
        f = get_trimmed_fastapath(msa)
        p = get_trimmed_phylippath(msa)
        
        fpath = get_raxml_fastapath(msa)
        ppath = get_raxml_phylippath(msa)
        
        os.system("cp " + f + " " + fpath)
        os.system("cp " + p + " " + ppath)       

def write_alignment_for_raxml(con):
    """This method finds the best set of alignment sites."""
    cur = con.cursor()
    
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        msaid = ii[0]
        msaname = ii[1]
        
        #
        # continue here --  to-do -- this section can be simplified by using SiteSetsAlignment
        # rather than all these indirect table calls
        #
        
        sql = "select treeid, max(mean_bootstrap) from FasttreeStats where treeid in "
        sql += "(select treeid from ZorroThreshFasttree where almethod=" + msaid.__str__() + ")"
        cur.execute(sql)
        y = cur.fetchall()
        best_treeid = y[0][0]
        #print "200:", msaid, best_treeid
        
        sql = "select thresh from ZorroThreshFasttree where treeid=" + best_treeid.__str__()
        cur.execute(sql)
        y = cur.fetchall()
        best_thresh = y[0][0]
        #best_thresh = 0.1
        #print "199:", msaid, best_thresh
        
        sql = "select min_score from ZorroThreshStats where thresh=" + best_thresh.__str__() + " and almethod=" + msaid.__str__()
        cur.execute(sql)
        min_score = cur.fetchone()[0]
        #print "211:", min_score
        
        """Get the sites."""
        sql = "select id from AlignmentSiteScoringMethods where name='zorro'"
        cur.execute(sql)
        zorromethod = cur.fetchone()[0]
        
        sql = "select site from AlignmentSiteScores where almethodid=" + msaid.__str__() + " and scoringmethodid=" +  zorromethod.__str__()
        sql += " and score >= " + min_score.__str__() + " order by site ASC"
        cur.execute(sql)
        y = cur.fetchall()
        sites = [] # a list of site indices into seed-trimmed sequences
        for ii in y:
            sites.append( ii[0] )
        #print "234:", seedsites[0], seedsites.__len__()
        
        # depricated
        #sql = "select setid from SiteSets where setname='seed'"
#         seedid = get_taxonid(con, ap.params["seed_motif_seq"] )
#         seedseq = get_aligned_seq(con, seedid, msaid)
#         start_motif = ap.params["start_motif"]
#         end_motif = ap.params["end_motif"]        
#         [start, stop] = get_boundary_sites(seedseq, start_motif, end_motif)
#         #print "243:", start, stop
#         
#         """Translate seed site numbers to original site numbers."""
#         sites = [] # a list of site indices into original sequences
#         for site in seedsites:
#             sites.append( site + start-1)
        
        #print "249:", sites[0], sites.__len__()
                
        fpath = get_raxml_fastapath(msaname)
        ppath = get_raxml_phylippath(msaname)
        
        """Write alignments"""
        ffout = open( fpath, "w")
        pfout = open( ppath, "w")

        sql = "select taxonid, alsequence from AlignedSequences where almethod=" + msaid.__str__()
        cur.execute(sql)
        y = cur.fetchall()
        pfout.write( y.__len__().__str__() + "   " + sites.__len__().__str__() + "\n")
        for jj in y: # for each sequence
            taxonid = jj[0]
            taxa = get_taxon_name(con, taxonid)
            seq = jj[1]
            finalseq = ""
            for site in sites:
                finalseq += seq[site-1]
            hasdata = False 
            for c in finalseq:
                if c != "-":
                    hasdata = True
            if hasdata == True: # Does this sequence contain at least one non-indel character?
                ffout.write(">" + taxa + "\n" + finalseq + "\n")
                pfout.write(taxa + "    " + finalseq + "\n")
            else:
                write_log(con, "After trimming the alignment " + msaid.__str__() + " to the ZORRO threshold, the taxa " + taxa + " contains no sequence content. This taxa will be obmitted from downstream analysis.")
        ffout.close()
        pfout.close()
        

def build_seed_sitesets(con, ap):
    cur = con.cursor()
    sql = "insert or replace into SiteSets(name) VALUES(\"seed\")"
    cur.execute(sql)
    con.commit()
    

def clear_sitesets(con, ap):
    cur = con.cursor()
    sql = "delete from SiteSets"
    cur.execute(sql)
    sql = "delete from SiteSetsAlignment"
    cur.execute(sql)
    con.commit()



def trim_alignments(con, ap):
    """Trims the alignment to match the start and stop motifs.
    The results are written as both PHYLIP and FASTA formats."""
    cur = con.cursor()
    
    """Create a SiteSet for the sites corresponding to the seed sequence(s)."""
    sql = "insert or replace into SiteSets(setname) VALUES('seed')"
    cur.execute(sql)
    con.commit()
    sql = "select id from SiteSets where setname='seed'"
    cur.execute(sql)
    sitesetid = cur.fetchone()[0]
    
    """Now iterate through each alignment, and find the start/stop sites
    corresponding to the seed sequence(s)."""
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        """Get the seed sequence, and then find the start and end sites."""
        alid = ii[0]
        alname = ii[1]        
        seedid = get_taxonid(con, ap.params["seed_motif_seq"] )
        seedseq = get_aligned_seq(con, seedid, alid)
        start_motif = ap.params["start_motif"]
        end_motif = ap.params["end_motif"]
                
        [start, stop] = get_boundary_sites(seedseq, start_motif, end_motif)
                
        """Remember these start and end sites."""
        sql = "insert or replace into SiteSetsAlignment(setid, almethod, fromsite, tosite) VALUES("
        sql += sitesetid.__str__() + "," + alid.__str__() + "," + start.__str__() + "," + stop.__str__() + ")"
        cur.execute(sql)
        con.commit()
        
        """Write an alignment, trimmed to the seed."""
        ffout = open( get_trimmed_fastapath(alname), "w")
        pfout = open( get_trimmed_phylippath(alname), "w")

        sql = "select taxonid, alsequence from AlignedSequences where almethod=" + alid.__str__()
        cur.execute(sql)
        y = cur.fetchall()
        pfout.write( y.__len__().__str__() + "   " + (stop-start+1).__str__() + "\n")
        for jj in y: # for each sequence
            taxonid = jj[0]
            taxa = get_taxon_name(con, taxonid)
            seq = jj[1]
            trimmed_seq = seq[start-1:stop]
            hasdata = False 
            for c in trimmed_seq:
                if c != "-":
                    hasdata = True
            if hasdata == True: # Does this sequence contain at least one non-indel character?
                ffout.write(">" + taxa + "\n" + trimmed_seq + "\n")
                pfout.write(taxa + "    " + trimmed_seq + "\n")
            else:
                write_log(con, "After trimming the alignment " + alid.__str__() + " to the seed boundaries, the taxa " + taxa + " contains no sequence content. This taxa will be obmitted from downstream analysis.")
        ffout.close()
        pfout.close()
    


def build_zorro_commands(con, ap):
    # 1. run ZORRO
    # 2. parse the results
    # 3. optimize the set of sites we draw from ZORRO, and the stability of the output tree
    # 4. write the final alignment
        
    cur = con.cursor()

    sql = "insert or replace into AlignmentSiteScoringMethods (name) VALUES('zorro')"
    cur.execute(sql)
    con.commit()
    
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()

    z_commands = []
    for ii in x:
        alid = ii[0]
        almethod = ii[1]
        """Write a script for ZORRO for this alignment."""
        c = ap.params["zorro_exe"] + " -sample " + get_trimmed_fastapath(almethod) + " > " + get_trimmed_fastapath(almethod) + ".zorro"
        z_commands.append( c )
    
    zorro_scriptpath = "SCRIPTS/zorro_commands.sh"
    fout = open(zorro_scriptpath, "w")
    for c in z_commands:
        fout.write( c + "\n" )
    fout.close()
    return zorro_scriptpath

def import_zorro_scores(con):
    cur = con.cursor()    
    
    sql = "delete from AlignmentSiteScores"
    cur.execute(sql)
    con.commit()

    sql = "select id from AlignmentSiteScoringMethods where name='zorro'"
    cur.execute(sql)
    x = cur.fetchall()
    if x.__len__() == 0:
        write_error(con, "301: There is something wrong with the database.")
        exit()
    zorroid = x[0][0]
    
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()

    """For each alignment, read & import the zorro scores."""
    for ii in x:
        alid = ii[0]
        almethod = ii[1]
        
        seedsetid = get_sitesetid(con, 'seed')
        minfromsite = get_lower_bound_in_siteset(con, seedsetid, alid)
        
        """Now offset all ZORRO sites by minfromsite, to account for the fact that the ZORRO
        analysis was performed on aligned sequences trimmed to the seed."""
        
        zorropath = get_trimmed_fastapath(almethod) + ".zorro"
        fin = open(zorropath, "r")
        site = minfromsite
        for line in fin.xreadlines():
            score = float( line.strip() )
            #print "326:", alid, site, score
            sql = "insert or replace into AlignmentSiteScores(almethodid,scoringmethodid,site,score) "
            sql += " VALUES(" + alid.__str__() + "," + zorroid.__str__() + "," + site.__str__() + "," + score.__str__() + ")"
            
            cur.execute(sql)
            site += 1
        con.commit()
        fin.close()
        
        sql = "select count(*) from AlignmentSiteScores where almethodid=" + alid.__str__() + " and scoringmethodid=" + zorroid.__str__()
        cur.execute(sql)
        count = cur.fetchone()[0]
        write_log(con, "I found " + count.__str__() + " ZORRO site scores for the alignment " + almethod.__str__())

def plot_zorro_stats(con):
    cur = con.cursor()
    
    sql = "select id from AlignmentSiteScoringMethods where name='zorro'"
    cur.execute(sql)
    zorroid = cur.fetchone()[0]
    
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        alid = ii[0]
        alname = ii[1]
        scores = get_alignmentsitescores(con, alid, zorroid)
        histogram(scores.values(), alname + "/zorro_scores", xlab="ZORRO score", ylab="proportion of sites")

def build_fasttree4zorro_commands(con):
    """Returns a scriptpath to FastTree commands."""
    cur = con.cursor()
    sql = "select id from AlignmentSiteScoringMethods where name='zorro'"
    cur.execute(sql)
    zorroid = cur.fetchone()[0]
    
    commands = []
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        alid = ii[0]
        alname = ii[1]
        commands += get_fasttree_zorro_commands_for_alignment(con, alid, zorroid)
    
    scriptpath = "SCRIPTS/zorro_fasttree_commands.sh"
    fout = open(scriptpath, "w")
    for c in commands:
        fout.write( c + "\n" )
    fout.close()
    return scriptpath

def get_fasttree_zorro_commands_for_alignment(con, almethod, scoringmethodid):
    """A helper method for get_best_zorro_set.
    Returns a list of commands for FastTree"""
    cur = con.cursor()
    sql = "select name from AlignmentMethods where id=" + almethod.__str__()
    cur.execute(sql)
    alname = cur.fetchone()[0]
    
    sql = "delete from ZorroThreshStats where almethod=" + almethod.__str__()
    cur.execute(sql)
    con.commit()
    
    
    """The sites in site_scores have been translated for the aligned sequence,
    rather than the trimmed-to-seed sequences."""
    site_scores = get_alignmentsitescores(con, almethod, scoringmethodid)
    nsites = site_scores.__len__()
    
        
    # debug moment
    #print "379:", almethod, min( site_scores.keys() ), max( site_scores.keys() )
     
    score_sites = {}
    for site in site_scores:
        this_score = site_scores[site]
        if this_score not in score_sites:
            score_sites[ this_score ] = []
        score_sites[ this_score ].append( site )
        
    sorted_scores = score_sites.keys()
    sorted_scores.sort( reverse=True )
    
    #print "409:", almethod, sorted_scores
    
    commands = []
    thresholds = get_setting_values(con, "zorro_threshold") # i.e., top 5%, 10%, 15% of scores
    thresholds.sort()

    for t in thresholds:
        """For each threshold:
            1. write a PHYLIP file containing an alignment of only those sites that satisfy the threshold.
            2. build a FastTree command to build a quick tree for this alignment.
        """
        
        sitesetname = "zorro:" + t.__str__()
        sitesetid = get_sitesetid(con, sitesetname)
        if sitesetid != None:      
            sql = "delete from SiteSetsAlignment where setid=" + sitesetid.__str__() + " and almethod=" + almethod.__str__()
            cur.execute(sql)
        elif sitesetid == None:
            """If there isn't a siteset for this threshold, then add one."""
            sql = "insert into SiteSets (setname) VALUES('" + sitesetname + "')"
            cur.execute(sql)
            sitesetid = get_sitesetid(con, sitesetname)
        con.commit()
                
        use_these_sites = []
        min_score = None
        for score in sorted_scores:
            if use_these_sites.__len__() < float(t)*float(nsites):
                use_these_sites += score_sites[score]
                if min_score == None:
                    min_score = score
                elif min_score > score:
                    min_score = score
        
        for site in use_these_sites:
            sql = "insert or replace into SiteSetsAlignment(setid, almethod, fromsite, tosite) "
            sql += " VALUES(" + sitesetid.__str__() + "," + almethod.__str__() + "," + site.__str__() + "," + site.__str__() + ")"
            cur.execute(sql)
        con.commit()
        write_log(con, "ZORRO details for " + alname + " -- threshold: " + t.__str__() + ", min score:" + min_score.__str__() + ", Nsites: " + use_these_sites.__len__().__str__() )

        sql = "insert into ZorroThreshStats(almethod, thresh, min_score, nsites)"
        sql += " VALUES(" + almethod.__str__() + "," + t.__str__() + "," + min_score.__str__() + "," + use_these_sites.__len__().__str__() + ")"
        cur.execute(sql)
        con.commit()

        """Write a PHYLIP with the aligned sequences containing only the threshold-ed sites."""        
        taxa_alseqs = get_sequences(con, almethod=almethod, sitesets=[sitesetid])# sites = use_these_sites)
        seqs = {}
        for taxonid in taxa_alseqs:
            tname = get_taxon_name(con, taxonid)
            seqs[tname] = taxa_alseqs[taxonid]    
            ppath = get_zorro_phylippath(alname, t)
            
            # debug moment:
            #print "461:", almethod, t, taxa_alseqs[taxonid]
            #aseq = get_aligned_seq(con, taxonid, almethod)
            #print "468:", aseq[  max( site_scores.keys() )-1  ]
            
        write_phylip(seqs, ppath)

        """Write a FastTree command to analyze these sites."""
        c = make_fasttree_command(con, ap, alname, ppath )
        #c = make_raxml_quick_command(con, ap, alname, ppath, alname + ".tmp.zorro." + t.__str__() )
        commands.append( c )
        
    return commands

def analyze_zorro_fasttrees(con):
    cur = con.cursor()
    sql = "select id from AlignmentSiteScoringMethods where name='zorro'"
    cur.execute(sql)
    zorroid = cur.fetchone()[0]
    
    sql = "delete from FasttreeStats"
    cur.execute(sql)
    con.commit()
    
    sql = "delete from ZorroThreshFasttree"
    cur.execute(sql)
    con.commit()
    
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        alid = ii[0]
        analyze_fasttrees_for_msa(con, alid)


def measure_fasttree_distances(con):
    cur = con.cursor()
    cur = con.cursor()
    sql = "delete from FasttreeSymmetricDistances"
    cur.execute(sql)
    sql = "delete from FasttreeRFDistances"
    cur.execute(sql)
    con.commit()
    
    sql = "select treeid, newick from ZorroThreshFasttree"
    cur.execute(sql)
    treeid_newick = {}
    x = cur.fetchall()
    for ii in x:
        treeid_newick[ii[0]] = ii[1]

    treeid_dendro = {}
    for ii in treeid_newick:
        print "515", ii
        t = Tree()
        t.read_from_string( treeid_newick[ii].__str__(), "newick")
        treeid_dendro[ii] = t
    
    ids = treeid_newick.keys()
    ids.sort()
    
    ii_jj_symd = {}
    ii_jj_rfd = {}
    for i in range(0, ids.__len__() ):
        ii = ids[i]
        ii_jj_symd[ii] = {}
        ii_jj_rfd[ii] = {}

        for j in range(i, ids.__len__()):
            jj = ids[j]
            """reciprocal symmetric difference"""
            ii_jj_symd[ii][jj] = treeid_dendro[ii].symmetric_difference( treeid_dendro[jj] ) + treeid_dendro[jj].symmetric_difference( treeid_dendro[ii] )
            sql = "insert into FasttreeSymmetricDistances(treeid1, treeid2, distance) VALUES("
            sql += ii.__str__() + "," + jj.__str__() + "," + ii_jj_symd[ii][jj].__str__() + ")"
            cur.execute(sql)
            ii_jj_rfd[ii][jj] = treeid_dendro[ii].robinson_foulds_distance( treeid_dendro[jj] )
            sql = "insert into FasttreeRFDistances(treeid1, treeid2, distance) VALUES("
            sql += ii.__str__() + "," + jj.__str__() + "," + ii_jj_rfd[ii][jj].__str__() + ")"
            cur.execute(sql)
            print "547:", ii, jj, ii_jj_symd[ii][jj], ii_jj_rfd[ii][jj]
    con.commit()
        

def analyze_fasttrees_for_msa(con, almethod):
    cur = con.cursor()
    sql = "select name from AlignmentMethods where id=" + almethod.__str__()
    cur.execute(sql)
    alname = cur.fetchone()[0] 
    thresholds = get_setting_values(con, "zorro_threshold")
    thresh_treepath = {}
    thresh_infopath = {}
    for t in thresholds:
        thresh_treepath[t] = get_fasttree_path( get_zorro_phylippath(alname, t) )
        if False == os.path.exists( thresh_treepath[t] ):
            write_error(con, "I can't find the FastTree tree for the ZORRO trial " + t.__str__() + " at path " + thresh_treepath[t] )
            exit()

        fin = open(thresh_treepath[t], "r")
        newick = fin.readline()
        fin.close()
        newick = newick.strip()
        sql = "insert into ZorroThreshFasttree(almethod, thresh, newick) VALUES(" + almethod.__str__()
        sql += ", " + t.__str__() + ",'" + newick + "')"
        cur.execute(sql)
        con.commit()

        """Get the randomly-generated new ID of the tree we just inserted."""
        sql = "select treeid from ZorroThreshFasttree where almethod=" + almethod.__str__() + " and thresh=" + t.__str__()
        cur.execute(sql)
        treeid = cur.fetchone()[0]

        mean_bs = get_mean( get_branch_supports(thresh_treepath[t]) )
        if mean_bs == None:
            mean_bs = 0.0
        sum_branches = get_sum_of_branches(thresh_treepath[t])
        sql = "insert or replace into FasttreeStats(treeid, mean_bootstrap, sum_of_branches) "
        sql += "VALUES(" + treeid.__str__() + "," + mean_bs.__str__() + "," + sum_branches.__str__() + ")"
        cur.execute(sql)
        con.commit()

        write_log(con, "Zorro threshold stat: " + alname + " thresh:" + t.__str__() + " branch_sum:" + sum_branches.__str__() + " mean_bs:" + mean_bs.__str__() )

def compare_fasttrees(con):
    cur = con.cursor()
    sql = "select id from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        msaid = ii[0]
        compare_fasttrees_for_alignment(con, msaid)


def compare_fasttrees_for_alignment(con, msaid):
    cur = con.cursor()
    sql = "select treeid, thresh from ZorroThreshFasttree where almethod=" + msaid.__str__()
    cur.execute(sql)
    x = cur.fetchall()
    thresh_treeid = {}
    for jj in x:
        treeid = jj[0]
        thresh = jj[1]
        thresh_treeid[ thresh ] = treeid
    
    threshes = thresh_treeid.keys()
    threshes.sort()

    """Plot RF distances"""
    for ii in range(0, threshes.__len__()):
        line = threshes[ii].__str__() + "\t"
        for jj in range(0, threshes.__len__()):
            sql = "select distance from FasttreeRFDistances where treeid1=" + thresh_treeid[ threshes[ii] ].__str__() + " and treeid2=" + thresh_treeid[  threshes[jj] ].__str__()
            cur.execute(sql)
            d = cur.fetchone()
            if d == None:
                sql = "select distance from FasttreeRFDistances where treeid1=" + thresh_treeid[ threshes[jj] ].__str__() + " and treeid2=" + thresh_treeid[  threshes[ii] ].__str__()
                cur.execute(sql)
                d = cur.fetchone()                
            line += "%.1f\t"%d
        print line
        
    """Plot Symmetric Distances"""
    for ii in range(0, threshes.__len__()):
        line = threshes[ii].__str__() + "\t"
        for jj in range(0, threshes.__len__()):
            sql = "select distance from FasttreeSymmetricDistances where treeid1=" + thresh_treeid[ threshes[ii] ].__str__() + " and treeid2=" + thresh_treeid[  threshes[jj] ].__str__()
            cur.execute(sql)
            d = cur.fetchone()
            if d == None:
                sql = "select distance from FasttreeSymmetricDistances where treeid1=" + thresh_treeid[ threshes[jj] ].__str__() + " and treeid2=" + thresh_treeid[  threshes[ii] ].__str__()
                cur.execute(sql)
                d = cur.fetchone()                
            line += "%.1f\t"%d
        print line 

        
def cleanup_zorro_analysis(con):
    """This method deletes the leftover files from the ZORRO analysis and the corresponding FastTree analysis."""
    cur = con.cursor()
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()

    """For each alignment, read & import the zorro scores."""
    for ii in x:
        alid = ii[0]
        almethod = ii[1]
        os.system("rm -rf " + almethod + "/" + almethod + ".*zorro*")

        