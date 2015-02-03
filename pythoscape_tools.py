import os
from asrpipelinedb_api import *

def run_similarity_network_analysis(con):

    #Import Pythoscape
    from pythoscape.auxiliary.re_patterns import RE_PATTERNS
    import pythoscape.main.environments as env
    import pythoscape.interface.local_interface as l_i
    
    #Import plug-ins
    import pythoscape.plugin.input.import_sequences as i_seq
    import pythoscape.plugin.input.add_local_blast as a_l_b
    import pythoscape.plugin.input.make_cdhit_repnodes as m_c_r
    import pythoscape.plugin.input.add_attribute_table as a_a_t
    import pythoscape.plugin.input.add_attribute_table as a_a_t
    import pythoscape.plugin.input_bio.import_structures as i_struc
    import pythoscape.plugin.input.repnode_stats as r_s
    import pythoscape.plugin.input.add_repnode_edges as a_r_e
    import pythoscape.plugin.input.add_repnode_atts as a_r_a
    import pythoscape.plugin.output.output_xgmml as o_x
    
    #Create interface and environment
    if False == os.path.exists("pythoscape"):
        os.system("mkdir pythoscape")
    
    sequences = {}
    cur = con.cursor()
    sql = "select taxonid, sequence from OriginalSequences where datatype=1"
    cur.execute(sql)
    for ii in cur.fetchall():
        taxonid = ii[0]
        aaseq = ii[1]
        sql = "select shortname from Taxa where id=" + taxonid.__str__()
        cur.execute(sql)
        taxonname = cur.fetchone()[0]
        sequences[taxonname] = aaseq
    
    fpath = "pythoscape/pythoscape_sequences.fasta"
    write_fasta(sequences, fpath)
    
    
    my_interface = l_i.LocalInterface("pythoscape")
    my_pytho = env.PythoscapeEnvironment(my_interface)
    
    #Create plug-ins
    
    #print dir(my_pytho)
    
    #print dir(my_pytho.graph_interface)
    
    #Import sequences
    #plugin_1 = i_s.ImportFromFastaFile(fpath, id_re=RE_PATTERNS['UniprotKB'], id_name='Uniprot')
    plugin_1 = i_seq.ImportFromFastaFile(fpath, id_name='Uniprot')

    blastp_exe = get_setting_values(con, "blastp_exe")
    if blastp_exe == None:
        write_log(con, "I can't find your BLAST executable. I'm skipping the similarity network analysis.")
        return
    blastp_exe = blastp_exe[0]
    plugin_2 = a_l_b.AddBLASTEdgesFromLocalBLAST("blastp", include_atts=['-log10(E)'])
    cdhit_exe = get_setting_values(con, "cdhit_exe")
    if cdhit_exe == None:
        write_log(con, "I canot find your CD-HIT executable. I'm skipping the similarity network analysis.")
        return
    
    cdhit_exe = cdhit_exe[0]
    repnode_att = "cdhit 0.7"
    network_name = "rep-net"
    plugin_4 = m_c_r.CreateCDHITRepnodes(network_name, "cd-hit", c=0.7, n=5, repnode_att=repnode_att)

    plugin_5 = r_s.CalcNodeSize(network_name,repnode_att,'node size')
    plugin_6 = a_r_e.AddEdgesToRepnodeNetwork(network_name,repnode_att,'-log10(E)',filt_dir='>',filt_value=0.0)
    plugin_7 = a_r_a.AddAttributesByIfAny(network_name,repnode_att,'family','repnode family')
    out_plugin_1 = o_x.OutputXGMML('gst-sigma-rep-net-20.xgmml','sigma gst representative node network @ 20',filt_name='rep-net mean',filt_dir='>',filt_value=20)
    
    
    #Execute plug-ins
    my_pytho.execute_plugin(plugin_1)
    my_pytho.execute_plugin(plugin_2)
    edge_query = my_interface.Edge()
    print "70:", len([True for edge in my_interface.pull(edge_query)])
    
    #Create representative network
    my_pytho.execute_plugin(plugin_4)
    my_pytho.execute_plugin(plugin_5)
    my_pytho.execute_plugin(plugin_6)
    my_pytho.execute_plugin(plugin_7)
    
    #Execute plug-ins
    my_net = env.PythoscapeNetwork(network_name,my_interface)
    my_net.execute_plugin(out_plugin_1)


def check_similarity_network_analysis(con):
    """This method validates that the output generated by the analysis in the method 'run_similarity_network_analysis'
        indeed did (or did not) complete correctly."""
    pass