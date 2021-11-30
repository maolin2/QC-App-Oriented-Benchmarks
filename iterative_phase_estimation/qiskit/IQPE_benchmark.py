"""
Phase Estimation Benchmark Program - Qiskit
"""

import sys
import time

import numpy as np
pi = np.pi 
from qiskit import Aer, QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.compiler import transpile
from qiskit.circuit.library.standard_gates import PhaseGate, MCPhaseGate


sys.path[1:1] = ["_common", "_common/qiskit"]
sys.path[1:1] = ["../../_common", "../../_common/qiskit"]
import execute as ex
import metrics as metrics

np.random.seed(0)

verbose = True # False

# saved subcircuits circuits for printing
QC_ = None
U_ = None

############### Circuit Definition

def IQPE_circ(qc0, U, ϕs, k):
    """The quantum circuit for the IQPE
    
    Args:
        qc0: Quantum circuit for the initial state |ψ>
        U: The gate used to estimate the phase
        ϕs: The digits previously measured
        k: The k-th iteration
        
    Note: 
        We don't include the circuit that create the state |ψ>
    
    """
    n = qc0.num_qubits
    qr = QuantumRegister(n+1)
    cr = ClassicalRegister(1)
    qc = QuantumCircuit(qr, cr)
#     qc = QuantumCircuit(qr)
    
    qc.append(qc0, qr[1:])
    
    ωk = 0
    for i, ϕ0 in enumerate(ϕs):
        ωk += ϕ0 * 2**(-(i+2))
    
    ωk = -2*pi * ωk
      
    qc.h(0)  
    p = 2**(k-1)

    Up = U.power(p).control(1, label=f"U^{p}") 
    
    qc.append(Up, qr)
    
    qc.rz(ωk, 0)
    qc.h(0)
    qc.measure(0, 0)

    # save smaller circuit example for display
    global QC_, U_
    if QC_ == None or n+1 <= 5:
        if n+1 < 9: QC_ = qc
    # if U_ == None or n+1 <= 5:
    #     if n+1 < 9: U_ = U
            
    return qc

def IQPE(qc0, U, m, backend = Aer.get_backend('qasm_simulator'), shots = 1000):
    """Use IQPE to estimate ϕ.
    
    Args:
        qc0: Quantum circuit for the initial state |ψ>
        U: The gate used to estimate the phase
        m: The number of digits for ϕ 
        backend: The backend used for IQPE
        shots: number of shots
    """
    
    n = qc0.num_qubits
    qr = QuantumRegister(n+1)
    qc = QuantumCircuit(qr)
    qc.append(qc0, qr[1:])

    ϕs = []
    counts_list = []
    for k in range(m, 0, -1):
#         qc.append(IQPE_circ(n, U, ϕs, k), qr)
        qc = IQPE_circ(qc0, U, ϕs, k)
        
        qc_transpile = transpile(qc, backend=backend, seed_transpiler=42, optimization_level=3)
        counts = backend.run(qc_transpile, shots = shots).result().get_counts()
        counts_list.append(counts)
        if '1' in counts:
            ϕs.insert(0, 1)
        else:
            ϕs.insert(0, 0)
        
    return ϕs, counts_list, qc
    
# Analyze and print measured results
def analyze_and_print_result(qc, result, num_qubits, k, num_shots):

    # get results as times a particular theta was measured
    counts = result.get_counts(qc)
    
    if verbose: print(f"For k = {k}, measured: {counts}")

    # correct distribution is measuring theta 100% of the time
    
    print(f"qc, result, num_qubits, k, num_shots = {qc, result, num_qubits, k, num_shots}")
    print(f"type(qc, result, num_qubits, k, num_shots) = {type(qc), type(result), type(num_qubits), type(k), type(num_shots)}")
    print(f"ϕs_={ϕs_}")

    correct_dist = {str(ϕs_[int(k)-1]): 1.0}

    # correct_dist = {'1': 1.0}

    # use our polarization fidelity rescaling
    fidelity = metrics.polarization_fidelity(counts, correct_dist)

    return counts, fidelity

################ Benchmark Loop

# Execute program with default parameters
def run(min_qubits=3, max_qubits=8, max_circuits=3, num_shots=100,
        backend_id='qasm_simulator', provider_backend=None,
        hub="ibm-q", group="open", project="main", exec_options=None):

    print("Iterative quantum phase estimation Benchmark Program - Qiskit")


    # Initialize metrics module
    metrics.init_metrics()

    def execution_handler(qc, result, ϕs, k, num_shots):

        # determine fidelity of result set
        counts, fidelity = analyze_and_print_result(qc, result, ϕs, k, num_shots)
        metrics.store_metric(qc.num_qubits, k, 'fidelity', fidelity)    

    # Initialize execution module using the execution result handler above and specified backend_id
    ex.init_execution(execution_handler)
    ex.set_execution_target(backend_id, provider_backend=provider_backend,
            hub=hub, group=group, project=project, exec_options=exec_options)

    # Execute Benchmark Program N times for multiple circuit sizes
    # Accumulate metrics asynchronously as circuits complete
    for num_qubits in range(min_qubits, max_qubits + 1):
        
        print(f"************\nExecuting [{max_circuits}] circuits with num_qubits = {num_qubits}")
        # randomly construct the phase ϕ 
        m = max_circuits
        ϕs = [0] * int(m/2) + [1] * (m-int(m/2))
        np.random.shuffle(ϕs)
        ϕ = sum([ϕ0 * 2**(-i-1) for i, ϕ0 in enumerate(ϕs)])

        # ϕs = [1]
        # ϕ = 0.5
        global ϕs_ 
        ϕs_ = ϕs

        # Construct the Unitary gate
        n = num_qubits - 1
        if n==1:
            U = PhaseGate(2*pi*ϕ)
        else:
            U = MCPhaseGate(2*pi*ϕ, n-1)

        # Construct the initial circuit 
        qc0 = QuantumCircuit(n, name = 'Xs')
        for i in range(qc0.num_qubits):
            qc0.x(i)

        
        for k in range(m, 0, -1):
            ts = time.time()

            ϕs2 = ϕs[k:]
            qc = IQPE_circ(qc0, U, ϕs2, k)

            # Do the transpile to make sure the circuit can be run on the backend
            backend = Aer.get_backend(backend_id)
            qc = transpile(qc, backend=backend, seed_transpiler=42, optimization_level=3)

            metrics.store_metric(num_qubits, k, 'create_time', time.time() - ts)

            # collapse the 3 sub-circuit levels used in this benchmark (for qiskit)
            qc2 = qc.decompose().decompose().decompose()
            
            # submit circuit for execution on target (simulator, cloud simulator, or hardware)
            ex.submit_circuit(qc2, num_qubits, k, num_shots)

        # Wait for some active circuits to complete; report metrics when groups complete
        ex.throttle_execution(metrics.finalize_group)

    # Wait for all active circuits to complete; report metrics when groups complete
    ex.finalize_execution(metrics.finalize_group)

    # print a sample circuit
    print("Sample Circuit:"); print(QC_ if QC_ != None else "  ... too large!")
    # print("\nPhase Operator 'U' = "); print(U_ if U_ != None else "  ... too large!")

    # Plot metrics for all circuit sizes
    metrics.plot_metrics("Benchmark Results - Iterative quantum phase estimation - Qiskit")

# if main, execute method
if __name__ == '__main__': run()
