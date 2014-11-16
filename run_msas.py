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
        if l.__len__() <= 1:
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
    taxa_seq[last_taxa] = last_seq
    fin.close()
    return taxa_seq

def import_and_clean_erg_seqs(con, ap):  
    """This method imports original sequences (unaligned) and builds entries
    in the SQL tables Taxa and OriginalSequences.
    Note: these tables are wiped clean before inserting new data."""  
    taxa_seq = read_fasta(ap.params["ergseqpath"])
    
    cur = con.cursor()
    sql = "delete from OriginalSequences"
    cur.execute(sql)
    sql = "delete from Taxa"
    cur.execute(sql)
    con.commit()
    
    for taxon in taxa_seq:
        import_original_seq(con, taxon, taxa_seq[taxon] )
    
    cleanpath = ap.params["ergseqpath"]
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
    
def write_msa_commands(con, ap):
    p = "SCRIPTS/msas.commands.sh"
    fout = open(p, "w")
    for msa in ap.params["msa_algorithms"]:
        if msa == "muscle":
            fout.write(ap.params["muscle_exe"] + " -maxhours 5 -in " + ap.params["ergseqpath"] + " -out " + get_fastapath(msa) + "\n")
            import_alignment_method(con, msa, ap.params["muscle_exe"])
        elif msa == "prank":
            fout.write(ap.params["prank_exe"] + " -d=" + ap.params["ergseqpath"] + " -o=" + get_fastapath(msa) + "\n")
            import_alignment_method(con, msa, ap.params["prank_exe"])
        elif msa == "msaprobs": 
            fout.write(ap.params["msaprobs_exe"] + " -num_threads 4 " + ap.params["ergseqpath"] + " > " + get_fastapath(msa) + "\n")
            import_alignment_method(con, msa, ap.params["msaprobs_exe"])
        elif msa == "mafft": 
            fout.write(ap.params["mafft_exe"] + " --thread 4 --auto " + ap.params["ergseqpath"] + " > " + get_fastapath(msa) + "\n")
            import_alignment_method(con, msa, ap.params["mafft_exe"])
    fout.close()
    return p
    #os.system("mpirun -np 4 --machinefile hosts.txt /common/bin/mpi_dispatch SCRIPTS/msas.commands.sh")

def check_aligned_sequences(con, ap):
    cur = con.cursor()
    for msa in ap.params["msa_algorithms"]:
        expected_fasta = get_fastapath(msa)
        if False == os.path.exists( expected_fasta ):
            write_error(con, "I can't find the expected FASTA output from " + msa + " at " + expected_fasta, code=None)
        taxa_seq = read_fasta(expected_fasta)
    
        if taxa_seq.__len__() == 0:
            write_error(con, "I didn't find any sequences in the alignment from " + msa)
            exit()
    
        sql = "select id from AlignmentMethods where name='" + msa + "'"
        cur.execute(sql)
        x = cur.fetchall()
        if x.__len__() == 0:
            write_error(con, "The alignment method " + msa + " does not exist in the database.")
            exit()
        almethodid = x[0][0] 

        sql = "delete from AlignedSequences where almethod=" + almethodid.__str__()
        cur.execute(sql)
        con.commit()

        for taxa in taxa_seq:
            taxonid = get_taxonid(con, taxa)
            import_aligned_seq(con, taxonid, almethodid, taxa_seq[taxa])
                 
        cur = con.cursor()
        sql = "select count(*) from AlignedSequences where almethod=" + almethodid.__str__()
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

def convert_all_fasta_to_phylip(ap):
    for msa in ap.params["msa_algorithms"]:
        f = get_fastapath(msa)
        p = get_phylippath(msa)
        fasta_to_phylip(f, p)
        f = get_trimmed_fastapath(msa)
        p = get_trimmed_phylippath(msa)
        fasta_to_phylip(f, p)


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
        
        #print "220:", alname, start, stop
        #print "221:", seedseq[start-1:stop]
        
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
        #print "305:", minfromsite
        
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
    thresholds = get_zorro_thresholds(con) # i.e., top 5%, 10%, 15% of scores
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

def analyze_zorro_fasttree(con):
    cur = con.cursor()
    sql = "select id from AlignmentSiteScoringMethods where name='zorro'"
    cur.execute(sql)
    zorroid = cur.fetchone()[0]
    
    sql = "select id, name from AlignmentMethods"
    cur.execute(sql)
    x = cur.fetchall()
    for ii in x:
        alid = ii[0]
        analyze_fasttrees(con, alid)

def analyze_fasttrees(con, almethod):
    cur = con.cursor()
    sql = "delete from ZorroThreshFasttreeStats where almethod=" + almethod.__str__()
    cur.execute(sql)
    con.commit()
    
    sql = "select name from AlignmentMethods where id=" + almethod.__str__()
    cur.execute(sql)
    alname = cur.fetchone()[0] 
    thresholds = get_zorro_thresholds(con)
    thresh_treepath = {}
    thresh_infopath = {}
    for t in thresholds:
        thresh_treepath[t] = get_fasttree_path( get_zorro_phylippath(alname, t) )
        if False == os.path.exists( thresh_treepath[t] ):
            write_error(con, "I can't find the FastTree tree for the ZORRO trial " + t.__str__() + " at path " + thresh_treepath[t] )
            exit()

        mean_bs = get_mean( get_branch_supports(thresh_treepath[t]) )
        sum_branches = get_sum_of_branches(thresh_treepath[t])
        sql = "insert or replace into ZorroThreshFasttreeStats(almethod, thresh, mean_bootstrap, sum_of_branches) "
        sql += "VALUES(" + almethod.__str__() + "," + t.__str__() + "," + mean_bs.__str__() + "," + sum_branches.__str__() + ")"
        cur.execute(sql)
        con.commit()

        write_log(con, "Zorro threshold stat: " + alname + " thresh:" + t.__str__() + " branch_sum:" + sum_branches.__str__() + " mean_bs:" + mean_bs.__str__() )

def cleanup_zorro_analysis(con):
    pass