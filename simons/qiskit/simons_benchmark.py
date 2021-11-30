"""
Bernstein-Vazirani Benchmark Program - Qiskit
"""

import sys
import time

import numpy as np
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

sys.path[1:1] = [ "_common", "_common/qiskit" ]
sys.path[1:1] = [ "../../_common", "../../_common/qiskit" ]
import execute as ex
import metrics as metrics

import itertools

np.random.seed(0)

verbose = False

# Variable for number of resets to perform after mid circuit measurements
num_resets = 1

# saved circuits for display
QC_ = None
Uf_ = None

############### Circuit Definition

def Simon_oracle(num_qubits, secret_int):

    # The size of the circuit is twice the input size
    input_size = int(num_qubits/2)

    # Initialize the oracle
    qr = QuantumRegister(num_qubits)
    qc = QuantumCircuit(qr, name=f"Uf")

    # perform a transversal CX to copy the input to the second register
    for ind in range(input_size):
        qc.cx(ind, ind + input_size)

    s = ('{0:0' + str(input_size) + 'b}').format(secret_int)

    # Find the first index where s[ind]=1
    ind_1 = None
    for ind, val in enumerate(s[::-1]):
        if val == '1':
            ind_1 = ind
            break

    # perform CX for each qubit that matches a bit in secret string
    if ind_1 == None:
        return qc
    
    for ind, val in enumerate(s[::-1]):
        if val == '1':
            qc.cx(ind_1, input_size+ind)
    return qc

def Simon(num_qubits, secret_int):
    
    # The size of the circuit is twice the input size    
    input_size = int(num_qubits/2)

    # allocate qubits
    qr = QuantumRegister(num_qubits)
    cr = ClassicalRegister(input_size)
    qc = QuantumCircuit(qr, cr, name="main")

    # Step 1: Apply Hadamard gates to all qubits in the first register
    for ind in range(input_size):
        qc.h(ind)
    qc.barrier()

    # Step2 : Generate Uf oracle
    Uf = Simon_oracle(num_qubits, secret_int)
    qc.append(Uf,qr)
    qc.barrier()

    # Step 3: Apply Hadamard gates to all qubits in the first register
    for ind in range(input_size):
        qc.h(ind)

    # Step 4: Measure the first register
    for ind in range(input_size):
        qc.measure(ind, ind)
    
    global Uf_
    if Uf_ == None or num_qubits <= 6:
        if num_qubits < 9: Uf_ = Uf

    # save smaller circuit example for display
    global QC_
    if QC_ == None or num_qubits <= 6:
        if num_qubits < 9: QC_ = qc

    # return a handle on the circuit
    return qc

def get_correct_dist(num_qubits, secret_int):
    
    lst1 = ["".join(i) for i in itertools.product(['0', '1'], repeat=int(num_qubits/2))] # All the available bit strings

    if secret_int==0:
        return dict(zip(lst1, [1/len(lst1) for _ in range(len(lst1))]))

    lst2 = [] # all the possible outcomes for nonzero secret_int
    secret_bin = format(secret_int, f"0{int(num_qubits/2)}b")

    def check_orth(bs):
        num_1 = sum([1 for i in range(len(bs)) if bs[i]=='1' and secret_bin[i]=='1'])
        if np.mod(num_1, 2)==0:
            return True
        else:
            return False
    
    for bs in lst1:
        if check_orth(bs) is True:
            lst2.append(bs)
        if len(lst2)== 2**(int(num_qubits/2)-1):
            break

    return dict(zip(lst2, [1/len(lst2) for _ in range(len(lst2))]))

############### Result Data Analysis

# Analyze and print measured results
# Expected result is always the secret_int, so fidelity calc is simple
def analyze_and_print_result (qc, result, num_qubits, secret_int, num_shots):

    # obtain counts from the result object
    counts = result.get_counts(qc)
    if verbose: print(f"For secret int {secret_int} measured: {counts}")

    # Get the correct distribution for the given num_qubits, and secret_int
    correct_dist = get_correct_dist(num_qubits, secret_int)

    # use our polarization fidelity rescaling
    fidelity = metrics.polarization_fidelity(counts, correct_dist)
        
    # print(f"counts={counts}")
    # print(f"correct_dist={correct_dist}")
    return counts, fidelity

################ Benchmark Loop

# Execute program with default parameters
def run (min_qubits=4, max_qubits=8, max_circuits=3, num_shots=100,
        backend_id='qasm_simulator', provider_backend=None,
        hub="ibm-q", group="open", project="main", exec_options=None):

    print("Simon's Benchmark Program - Qiskit")

    # validate min_qubits, max_qubits are even integers
    if np.mod(min_qubits,2) != 0 or np.mod(max_qubits,2) != 0:
        raise ValueError("`min_qubits` or `max_qubits` has to be even.")

    # validate parameters (smallest circuit is 4 qubits)
    max_qubits = max(4, max_qubits)
    min_qubits = min(max(4, min_qubits), max_qubits)
    #print(f"min, max qubits = {min_qubits} {max_qubits}")

    # Variable for new qubit group ordering if using mid_circuit measurements
    mid_circuit_qubit_group = []

    # If using mid_circuit measurements, set transform qubit group to true
    transform_qubit_group = False
    
    # Initialize metrics module
    metrics.init_metrics()

    # Define custom result handler
    def execution_handler(qc, result, num_qubits, s_int, num_shots):  
     
        # determine fidelity of result set
        num_qubits = int(num_qubits)
        counts, fidelity = analyze_and_print_result(qc, result, num_qubits, int(s_int), num_shots)
        metrics.store_metric(num_qubits, s_int, 'fidelity', fidelity)

    # Initialize execution module using the execution result handler above and specified backend_id
    ex.init_execution(execution_handler)
    ex.set_execution_target(backend_id, provider_backend=provider_backend,
            hub=hub, group=group, project=project, exec_options=exec_options)

    # for noiseless simulation, set noise model to be None
    # ex.set_noise_model(None)

    # Execute Benchmark Program N times for multiple circuit sizes
    # Accumulate metrics asynchronously as circuits complete
    for num_qubits in range(min_qubits, max_qubits+1, 2):
        input_size = int(num_qubits/2)
        
        # determine number of circuits to execute for this group
        num_circuits = min(2**(input_size), max_circuits)
        
        print(f"************\nExecuting [{num_circuits}] circuits with num_qubits = {num_qubits}")
        
        # determine range of secret strings to loop over
        if 2**(input_size) <= max_circuits:
            s_range = list(range(num_circuits))
        else:
            s_range = np.random.choice(2**(input_size), num_circuits, False)

        # loop over limited # of secret strings for this
        for s_int in s_range:

            # create the circuit for given qubit size and secret string, store time metric
            ts = time.time()
            qc = Simon(num_qubits, s_int)
            metrics.store_metric(num_qubits, s_int, 'create_time', time.time()-ts)

            # collapse the sub-circuit levels used in this benchmark (for qiskit)
            qc2 = qc.decompose()

            # submit circuit for execution on target (simulator, cloud simulator, or hardware)
            ex.submit_circuit(qc2, num_qubits, s_int, shots=num_shots)
        
        # Wait for some active circuits to complete; report metrics when groups complete
        ex.throttle_execution(metrics.finalize_group)
        
    # Wait for all active circuits to complete; report metrics when groups complete
    ex.finalize_execution(metrics.finalize_group)

    # print a sample circuit
    print("Sample Circuit:"); print(QC_ if QC_ != None else "  ... too large!")
    print("\nQuantum Oracle 'Uf' ="); print(Uf_ if Uf_ != None else " ... too large!")

    # Plot metrics for all circuit sizes
    metrics.plot_metrics(f"Benchmark Results - Simons - Qiskit",
                         transform_qubit_group = transform_qubit_group, new_qubit_group = mid_circuit_qubit_group)

# if main, execute method
if __name__ == '__main__': run()
   
