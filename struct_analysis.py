import os, sys, time
from configuration import *
from tools import *
from phyloxml_helper import *
from asr_dat_to_seq import *

PDBDIR = "pdb"

def write_ancseq_fasta(ap):
    """Writes a FASTA file into the PDBDIR, containing
    the sequences for all the ancestors listed with an ingroup
    in the configuration file."""
    if os.path.exists(PDBDIR) == False:
        os.system("mkdir " + PDBDIR)
    
    fout = open(PDBDIR + "/ancseqs.fasta", "w")
            
    for model in ap.params["raxml_models"]:
        for msa in ap.params["msa_algorithms"]:
            for anc in ap.params["ingroup"]:
                datpath = msa + "/asr." + model + "/" + anc + ".dat"
                probs = getprobs(datpath)
                mls = get_ml_sequence(probs)
                fout.write(">" + datpath + "\n")
                fout.write(mls + "\n")
    fout.close()