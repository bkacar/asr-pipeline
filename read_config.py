import re,sys,os
from tools import *
from log import *

def read_config_file(ap):
    """This method reads the user-written configuration file.
    The format of the file is generally KEYWORD = VALUE,
    where KEYWORD can be a limited set of parameters, such as GENEID or RAXML,
    and VALUE is the corresponding parameter value.
    
    For more information about valid KEYWORDs and VALUEs, see the user documentation,
    or simply read this method and look for lines containing if tokens[0].startswith("...")
    
    """
    cpath = ap.getArg("--configpath")
    print "7:", cpath
    if False == os.path.exists("./" + cpath):
        print "ERROR: I can't find your configfile at", cpath
        write_error(ap, "I can't find your configfile at " + cpath)
        exit()
    
    fin = open(cpath, "r")

    # Default values:
    #
    ap.params["end_motif"] = None
    ap.params["start_motif"] = None
    ap.params["constraint_tree"] = None

    for l in fin.xreadlines():
        l = l.strip()
        if l.startswith("#"):
            continue
        if l.__len__() < 2:
            continue
        tokens = l.split("=")
        if tokens.__len__() < 1: 
            continue
        
        if tokens[0].startswith("GENE_ID"):
            ap.params["geneid"] = re.sub(" ", "", tokens[1])
        
        if tokens[0].startswith("PROJECT_TITLE"):
            ap.params["project_title"] = tokens[1]

        if tokens[0].startswith("SEQUENCES"):
            ap.params["ergseqpath"] = re.sub(" ", "", tokens[1])
        
        elif tokens[0].startswith("RAXML"):
            ap.params["raxml_exe"] = tokens[1].strip()
        
        elif tokens[0].startswith("PHYML"):
            ap.params["phyml_exe"] = tokens[1].strip()

        elif tokens[0].startswith("LAZARUS"):
            ap.params["lazarus_exe"] = tokens[1].strip()

        elif tokens[0].startswith("MARKOV_MODEL_FOLDER"):
            ap.params["mmfolder"] = tokens[1].strip()
        
        elif tokens[0].startswith("MPIRUN"):
            ap.params["mpirun_exe"] = tokens[1]
        
        elif tokens[0].startswith("RUN"):
            ap.params["run_exe"] = tokens[1]
        
        elif tokens[0].startswith("MSAPROBS"):
            ap.params["msaprobs_exe"] = tokens[1].strip()

        elif tokens[0].startswith("MUSCLE"):
            ap.params["muscle_exe"] = tokens[1].strip()

        elif tokens[0].startswith("PRANK"):
            ap.params["prank_exe"] = tokens[1].strip()
        
        elif tokens[0].startswith("ANCCOMP"):
            ap.params["anccomp"] = tokens[1].strip()
        
        elif tokens[0].startswith("PYMOL"):
            ap.params["pymol_exe"] = tokens[1].strip()
        
        elif tokens[0].startswith("ALIGNMENT_ALGORITHMS"):
            x = tokens[1].split()
            ap.params["msa_algorithms"] = []
            for i in x:
                ap.params["msa_algorithms"].append( i )
        
        elif tokens[0].startswith("MODELS_RAXML"):
            x = tokens[1].split()
            ap.params["raxml_models"] = []
            for i in x:
                ap.params["raxml_models"].append( i )
        
        elif tokens[0].startswith("START_MOTIF"):
            ap.params["start_motif"] = re.sub(" ", "", tokens[1])
            if ap.params["start_motif"].__contains__("None"):
                ap.params["start_motif"] = None 
        
        elif tokens[0].startswith("END_MOTIF"):
            ap.params["end_motif"] = re.sub(" ", "", tokens[1])
            if ap.params["end_motif"].__contains__("None"):
                ap.params["end_motif"] = None 
 
        elif tokens[0].startswith("CONSTRAINT_TREE"):
            ap.params["constraint_tree"] = re.sub(" ", "", tokens[1])
            if False == os.path.exists(ap.params["constraint_tree"]):
                print "\n. I can't find your constraint tree at", ap.params["constraint_tree"]
                exit()

        elif tokens[0].startswith("FAMILY_DESCRIPTION"):
            ap.params["family_description"] = tokens[1] 
 
# depricated: 
# continue here... and look in the msa get_bondary_sites function      
        elif tokens[0].startswith("SEED"):
            ap.params["seed_motif_seq"] = re.sub(" ", "", tokens[1])
        
        elif tokens[0].startswith("N_BAYES_SAMPLES"):
            ap.params["n_bayes_samples"] = int(tokens[1])
        
        elif tokens[0].startswith("OUTGROUP"):
            ap.params["outgroup"] = re.sub(" ", "", tokens[1])

# depricated:
#        elif tokens[0].startswith("ANCESTORS"):
#            x = tokens[1].split()
#            ap.params["ancestors"] = []
#            for i in x:
#                ap.params["ancestors"].append( i )
        
        elif tokens[0].startswith("INGROUP"):
            if "ingroup" not in ap.params:
                ap.params["ingroup"] = {}
            anc = tokens[0].split()[1]
            ingroup = tokens[0].split()[2:]
            ingroup = "".join(ingroup)
            ingroup = re.sub(" ", "", ingroup) # tolerate and remove whitespace.
            ap.params["ingroup"][ anc ] = ingroup
        
        elif tokens[0].startswith("ASRSEED"):
            if "seedtaxa" not in ap.params:
                ap.params["seedtaxa"] = {}
            ts = tokens[0].split()
            anc = ts[1]
            seed = ts[2]
            ap.params["seedtaxa"][ anc ] = re.sub(" ", "", seed)

        elif tokens[0].startswith("COMPARE"):
            anc1 = tokens[0].split()[1]
            anc2 = tokens[0].split()[2]
            if "compareanc" not in ap.params:
                ap.params["compareanc"] = []
            ap.params["compareanc"].append( (anc1,anc2) )
            
        elif tokens[0].startswith("USE_MPI"):
            print tokens[1]
            answer = re.sub(" ", "", tokens[1])
            if answer == "on" or answer == "True":
                ap.params["usempi"] = True
            else:
                ap.params["usempi"] = False
        
        elif tokens[0].startswith("PHYRE_OUTPUT"):
            ap.params["phyre_out"] = re.sub("\ ", "", tokens[1])
            ap.params["phyre_out"].strip()

        elif tokens[0].startswith("PDBTOOLSDIR"):
            ap.params["pdbtoolsdir"] = re.sub("\ ", "", tokens[1])
            ap.params["pdbtoolsdir"].strip()

        elif tokens[0].startswith("PYMOL"):
            ap.params["pymol_exe"] = tokens[1].strip()

        elif tokens[0].startswith("MAP2PDB"): # map Df scores for this ancestor onto the PDB path
            anc = tokens[0].split()[1]
            pdbpath = tokens[0].split()[2]
            if "map2pdb" not in ap.params:
                ap.params["map2pdb"] = {}
            if anc not in ap.params["map2pdb"]:
                ap.params["map2pdb"][anc] = []
            if pdbpath not in ap.params["map2pdb"][anc]:
                ap.params["map2pdb"][ anc ].append( pdbpath )
        
        elif tokens[0].startswith("HTML_SPECIAL1"):
            thing = ""
            for i in range(1, tokens.__len__()):
                t = tokens[i]
                if i < tokens.__len__()-1:
                    thing += t + "="
                else:
                    thing +=  t
            ap.params["HTML_SPECIAL1"] = thing
    
    fin.close()

def verify_config(ap):
    """Will return nothing if the configuration is ok.  Will error and quit if the
    configuration is flawed."""
    
    if "run_exe" not in ap.params:
        ap.params["run_exe"] = "source"
    
    if "ancestors" in ap.params:
        for a in ap.params["ancestors"]:
            print a, ap.params["seedtaxa"]
            if a not in ap.params["seedtaxa"]:
                print "\n. ERROR: You did not specify a SEED for the ancestor", a
                write_error(ap, "You did not specify a SEED for the ancestor " + a)
                exit()
        for c in ap.params["compareanc"]:
            a1 = c[0]
            a2 = c[1]
            if a1 not in ap.params["ancestors"]:
                print "\n. ERROR: you specified a comparison between ancestors", a1, "and", a2, "but", a1,"was not defined in the ANCESTORS line."
                write_error(ap, "you specified a comparison between ancestors " + a1, " and " + a2 + " but " + a1 + " was not defined in the ANCESTORS line.") 
                exit() 
            if a1 not in ap.params["ancestors"]:
                print "\n. ERROR: you specified a comparison between ancestors", a1, "and", a2, "but", a2,"was not defined in the ANCESTORS line."
                write_error(ap, "you specified a comparison between ancestors " + a1, " and " + a2 + " but " + a2 + " was not defined in the ANCESTORS line.")
                exit()
                
    if False == os.path.exists(ap.params["ergseqpath"]):
        print "\n. I could not find your sequences at", ap.params["ergseqpath"]
        write_error(ap, "I could not find your sequences at " + ap.params["ergseqpath"])
        exit()

    if ap.params["start_motif"] == None:
        ap.params["start_motif"] = ""
    if ap.params["end_motif"] == None:
        ap.params["end_motif"] = ""
        
    for msa in ap.params["msa_algorithms"]:
        if msa == "MUSCLE" and "muscle_exe" not in ap.params:
            print "\n. Something is wrong. Your config file doesn't have an executable path for MUSCLE."
            write_error(ap, "Something is wrong. Your config file doesn't have an executable path for MUSCLE.")
            exit()
        if msa == "MSAPROBS" and "msaprobs_exe" not in ap.params:
            print "\n. Something is wrong. Your config file doesn't have an executable path for MSAPROBS."
            write_error(ap, "Something is wrong. Your config file doesn't have an executable path for MSAPROBS.")
            exit()
        if msa == "PRANK" and "prank_exe" not in ap.params:
            print "\n. Something is wrong. Your config file doesn't have an executable path for PRANK."
            write_error(ap, "Something is wrong. Your config file doesn't have an executable path for PRANK.")
            exit()
    
    if "map2pdb" not in ap.params:
        ap.params["map2pdb"] = {}
        
    if "pdbtoolsdir" in ap.params and "pymol_exe" in ap.params:
        ap.params["do_pdb_analysis"] = True
    else:
        ap.params["do_pdb_analysis"] = False
    
    return ap

def print_config(ap):
    for p in ap.params:
        print p, ":", ap.params[p]

def setup_workspace(ap):
    for msa in ap.params["msa_algorithms"]:
        if False == os.path.exists(msa):
            os.system("mkdir " + msa)
        if False == os.path.exists(msa):
            print "I can't make the directory for output of " + msa
            write_error(ap, "I can't make the directory for output of " + msa)
            exit()
    if False == os.path.exists("SCRIPTS"):
        os.system("mkdir SCRIPTS")
            