# decider_tk.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socketio
import numpy as np
import math

# Put here the coordinator address the decider should connect to.
# If coordinator runs on another PC, set SERVER_WS = "http://192.168.x.y:5003"
SERVER_WS = "http://192.168.1.19:5003"

# Structure: [weight, P, Q, V] for each criterion (index order expected by UI)
DECIDER_PREFS = {
    "decider_policeman": [
        [7.51, 0.6, 0.3, 1],
        [13.63, 0.6, 0.3, 0.8],
        [13.63, 0, 0, 0],
        [13.63, 110, 55, 220],
        [17.2, 10, 5, 20],
        [17.2, 0.6, 0.3, 1.2],
        [17.2, 0.6, 0.3, 1.5],
    ],
    "decider_economist": [
        [17.38, 0.5, 0.25, 1],
        [29.4, 0.6, 0.3, 1.2],
        [6.16, 0.3, 0.15, 0.6],
        [6.16, 99, 45, 180],
        [6.16, 6, 3, 12],
        [17.38, 0.5, 0.25, 1],
        [17.38, 0.5, 0.25, 1],
    ],
    "decider_environmental representative": [
        [4.96, 0.7, 0.35, 1.4],
        [7.08, 0.7, 0.35, 1.4],
        [17.31, 0.6, 0.3, 1.2],
        [18.93, 100, 50, 200],
        [18.93, 8, 4, 16],
        [17.52, 1, 0.5, 2],
        [15.27, 0.7, 0.35, 1.4],
    ],
    "decider_public representative": [
        [6.15, 0.4, 0.2, 0.8],
        [19.57, 0.4, 0.2, 0.8],
        [13.79, 0.2, 0.1, 0.4],
        [13.79, 60, 30, 120],
        [13.79, 4, 2, 8],
        [16.45, 0.6, 0.15, 0.6],
        [16.45, 0.4, 0.2, 0.8],
    ],
}

# Fixed list of criteria names for display (UI only)
CRITERIA_NAMES = ["Nuisances", "Noise", "Impacts", "Geotechnics", "Equipment", "Accessibility", "Climate"]

def _send_final_result(self, phi, ranking_idx):
    try:
        ranking_list = [int(i) for i in ranking_idx]

        payload = {
            "decider": self.name,
            "phi": phi.tolist(),
            "ranking": ranking_list
        }

        self.sio.emit("final_ranking", payload)
        messagebox.showinfo("Success", "Final ranking sent to coordinator! 🎉")
    except Exception as e:
        messagebox.showerror("Error", f"Cannot send result: {e}")
        
def _to_float_safe(x):
    """
    Try to convert x to float. Accepts strings with comma decimal separators.
    Returns float or raises ValueError.
    """
    if x is None:
        raise ValueError("None")
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    # replace comma decimal if present, but avoid replacing thousand separators like '1,234'
    # heuristic: if there's exactly one comma and no dots -> treat comma as decimal sep
    if s.count(",") == 1 and s.count(".") == 0:
        s2 = s.replace(",", ".")
    else:
        # remove spaces and non-numeric characters except dot and minus
        s2 = s.replace(" ", "")
        # also replace comma if it looks like decimal (e.g., '0,68')
        s2 = s2.replace(",", ".")
    # keep only digits, dot, minus and exponent parts
    allowed = "0123456789.-+eE"
    s3 = "".join(ch for ch in s2 if ch in allowed)
    if s3 == "" or s3 in {".", "-", "+", "+.", "-."}:
        raise ValueError(f"cannot parse '{x}' to float")
    return float(s3)


class PrometheeCalculator:
    """
    Lightweight PROMETHEE II calculator.
    Expects:
      - perf: numpy array shape (n_actions, n_criteria) numeric
      - weights: list/array of size m (weights per criterion)
      - P_list, Q_list: lists per criterion (P = strict pref threshold, Q = indifference)
    """
    def __init__(self, perf, weights, P_list, Q_list):
        self.perf = np.array(perf, dtype=float)
        self.n, self.m = self.perf.shape
        self.weights = np.array(weights, dtype=float)
        self.P = np.array(P_list, dtype=float)
        self.Q = np.array(Q_list, dtype=float)
        # sum weights
        self.wsum = float(np.sum(self.weights)) if self.weights.size > 0 else 1.0

    def _pi_linear(self, d, Pk, Qk):
        # vectorized linear preference: d may be scalar or array
        # return value between 0 and 1
        if Pk == Qk:
            # avoid division by zero; step function
            return np.where(d > Pk, 1.0, 0.0)
        res = np.zeros_like(d, dtype=float)
        # d <= Q -> 0 (already zero)
        mask_mid = (d > Qk) & (d < Pk)
        res[mask_mid] = (d[mask_mid] - Qk) / (Pk - Qk)
        res[d >= Pk] = 1.0
        return res

    def compute_action_action_matrix(self):
        n = self.n
        Pi = np.zeros((n, n), dtype=float)
        # for each criterion compute pi_k(Ai,Aj)
        for k in range(self.m):
            fk = self.perf[:, k]  # shape (n,)
            Pk = self.P[k]
            Qk = self.Q[k]
            wk = self.weights[k]
            # compute differences matrix d_ij = f_i - f_j
            d = fk.reshape((n, 1)) - fk.reshape((1, n))  # shape (n,n)
            # apply preference function (vectorized)
            pi_k = self._pi_linear(d, Pk, Qk)  # shape (n,n)
            # weighted accumulation
            Pi += wk * pi_k
        # normalize by sum of weights
        if self.wsum != 0:
            Pi = Pi / self.wsum
        return Pi

    def compute_flows_and_ranking(self, Pi):
        n = Pi.shape[0]
        phi_plus = np.sum(Pi, axis=1) / (n - 1)
        phi_minus = np.sum(Pi, axis=0) / (n - 1)
        phi = phi_plus - phi_minus
        ranking_idx = np.argsort(-phi)  # descending
        return phi_plus, phi_minus, phi, ranking_idx


class DeciderApp:
    def __init__(self, root, name):
        self.root = root
        self.name = name
        self.root.title(f"DECIDER - {name}")
        self.root.geometry("750x520")

        top = ttk.Frame(root)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text=f"Decider: {name}", font=("Arial", 14, "bold")).pack(side="left")

        self.status = ttk.Label(root, text="⏳ Waiting for coordinator...", foreground="gray")
        self.status.pack(fill="x", padx=8, pady=4)

        # Treeview to display the matrix as received (with headers)
        self.tree = ttk.Treeview(root, show="headings")
        self.tree.pack(fill="both", expand=True, padx=8, pady=6)

        # Buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(fill="x", padx=8, pady=6)
        self.pref_btn = ttk.Button(btn_frame, text="Show Preferences", command=self.show_preferences, state="disabled")
        self.pref_btn.pack(side="left", padx=4)
        self.promethee_btn = ttk.Button(btn_frame, text="PROMETHEE", command=self.run_promethee, state="disabled")
        self.promethee_btn.pack(side="left", padx=4)

        # socketio client
        self.sio = socketio.Client(logger=False, reconnection=True)
        self.sio.on("matrix_update", self._on_matrix_update)
        self.sio.on("connect", lambda: self._log("🟢 Connected to server – waiting for matrix..."))
        self.sio.on("disconnect", lambda: self._log("🔴 Disconnected from server"))

        t = threading.Thread(target=self._start_socketio, daemon=True)
        t.start()

        # internal storage
        self.actions = []            # list of action names (strings)
        self.criteria_headers = []   # list of criteria headers (strings)
        self.performance_matrix = None  # numpy array numeric (n_actions x n_criteria)
        self.promethee_results = None

    def _start_socketio(self):
        try:
            self.sio.connect(SERVER_WS)
            self.sio.wait()
        except Exception as err:
            # show error in UI thread
            self.root.after(0, lambda err=err: self._log(f"SocketIO connection error: {err}"))

    def _log(self, msg):
        self.status.config(text=msg)

    def _on_matrix_update(self, payload):
        # payload expected to be {"matrix": matrix}
        matrix = payload.get("matrix") if isinstance(payload, dict) else payload
        if not matrix:
            return
        # schedule update in main thread
        self.root.after(0, lambda: self._show_matrix(matrix))

    def _show_matrix(self, matrix):
        """
        Display the received matrix in the Treeview.
        Expect a matrix where:
          - matrix[0] is header row (first cell maybe 'Actions', rest criteria)
          - matrix[1:] rows, first column are action names, rest are numeric values
        We keep the visual display intact but extract numeric submatrix for PROMETHEE.
        """
        # clear tree
        for c in self.tree.get_children():
            self.tree.delete(c)
        # derive columns count
        if not matrix or not matrix[0]:
            messagebox.showerror("Error", "Received empty or malformed matrix.")
            return
        num_cols = len(matrix[0])
        # prepare column identifiers
        cols = [f"col{i}" for i in range(num_cols)]
        self.tree["columns"] = cols
        # set headings from first row of matrix (if present)
        header_row = matrix[0]
        for idx, col_id in enumerate(cols):
            heading = header_row[idx] if idx < len(header_row) else f"Col {idx+1}"
            self.tree.heading(col_id, text=str(heading))
            self.tree.column(col_id, width=110, anchor="center")

        # insert all rows for display
        for row in matrix[1:]:  # show from second row onward (avoid duplicating header)
            # ensure row has correct length
            row_display = [row[i] if i < len(row) else "" for i in range(num_cols)]
            self.tree.insert("", "end", values=row_display)

        # parse numeric performance data (ignore header row and first column)
        actions = []
        criteria_headers = header_row[1:]  # skip first col (Actions)
        numeric_rows = []
        for r in matrix[1:]:
            # first column is action name
            if not r:
                continue
            action_name = str(r[0]) if len(r) > 0 else ""
            actions.append(action_name)
            # numeric cells start at index 1
            numeric_cells = []
            for cell in r[1:]:
                try:
                    val = _to_float_safe(cell)
                    numeric_cells.append(val)
                except Exception:
                    # if a cell can't parse, put nan
                    numeric_cells.append(float("nan"))
            numeric_rows.append(numeric_cells)

        # convert to numpy array and drop columns that are all NaN or missing to match DECIDER_PREFS length
        if numeric_rows and any(len(row) > 0 for row in numeric_rows):
            # pad rows to same length
            max_len = max(len(r) for r in numeric_rows)
            padded = [r + [float("nan")] * (max_len - len(r)) for r in numeric_rows]
            perf = np.array(padded, dtype=float)
            # if matrix has extra columns beyond number of criteria we expect, trim to first len(CRITERIA_NAMES)
            expected_m = len(CRITERIA_NAMES)
            if perf.shape[1] >= expected_m:
                perf = perf[:, :expected_m]
                criteria_headers = criteria_headers[:expected_m]
            else:
                # if fewer columns, ok, we'll use what exists
                pass
            # store
            self.actions = actions
            self.criteria_headers = criteria_headers
            self.performance_matrix = perf
            self._log(f"✅ Matrix received ({perf.shape[0]} actions x {perf.shape[1]} criteria).")
        else:
            self.performance_matrix = None
            self.actions = []
            self.criteria_headers = []
            self._log("⚠️ No numeric performance data found in matrix.")

        # enable buttons
        self.pref_btn.config(state="enabled")
        self.promethee_btn.config(state="enabled")

    def show_preferences(self):
        prefs = DECIDER_PREFS.get(self.name.lower())
        if not prefs:
            messagebox.showerror("Error", f"No preferences found for {self.name}")
            return

        pref_window = tk.Toplevel(self.root)
        pref_window.title(f"{self.name}'s Preferences")
        pref_window.geometry("600x320")
        ttk.Label(pref_window, text=f"Subjective parameters of {self.name}", font=("Arial", 12, "bold")).pack(pady=8)

        cols = ["Criteria", "Weight", "P", "Q", "V"]
        tree = ttk.Treeview(pref_window, columns=cols, show="headings", height=8)
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, anchor="center", width=100)
        tree.pack(padx=10, pady=10, fill="both", expand=True)

        # use CRITERIA_NAMES for display
        for crit_name, vals in zip(CRITERIA_NAMES, prefs):
            tree.insert("", "end", values=[crit_name] + vals)

        ttk.Button(pref_window, text="Close", command=pref_window.destroy).pack(pady=8)

    # PROMETHEE UI & logic
    def run_promethee(self):
        if self.performance_matrix is None:
            messagebox.showwarning("Warning", "No numeric data available for PROMETHEE calculation.")
            return

        # Build weights, P_list, Q_list from DECIDER_PREFS for this decider
        prefs = DECIDER_PREFS.get(self.name.lower())
        if not prefs:
            messagebox.showerror("Error", f"No preferences found for {self.name}")
            return

        # create arrays (trim to available number of criteria)
        m_available = min(self.performance_matrix.shape[1], len(prefs))
        weights = [prefs[i][0] for i in range(m_available)]
        P_list = [prefs[i][1] for i in range(m_available)]
        Q_list = [prefs[i][2] for i in range(m_available)]

        calc = PrometheeCalculator(self.performance_matrix[:, :m_available], weights, P_list, Q_list)
        Pi = calc.compute_action_action_matrix()  # action-action matrix
        phi_plus, phi_minus, phi, ranking_idx = calc.compute_flows_and_ranking(Pi)

        # store results for UI buttons
        self.promethee_results = {
            "Pi": Pi,
            "phi_plus": phi_plus,
            "phi_minus": phi_minus,
            "phi": phi,
            "ranking_idx": ranking_idx,
        }

        # show control window with 3 buttons
        win = tk.Toplevel(self.root)
        win.title(f"PROMETHEE - {self.name}")
        win.geometry("360x220")
        ttk.Label(win, text=f"{self.name} — PROMETHEE results", font=("Arial", 12, "bold")).pack(pady=8)

        ttk.Button(win, text="Agrégation (Action–Action matrix)", command=self._show_pi_window).pack(pady=6, fill="x", padx=12)
        ttk.Button(win, text="Exploitation (Flows)", command=self._show_flows_window).pack(pady=6, fill="x", padx=12)
        ttk.Button(win, text="Rangement final (Ranking)", command=self._show_ranking_window).pack(pady=6, fill="x", padx=12)

    def _show_pi_window(self):
        Pi = self.promethee_results["Pi"]
        n = Pi.shape[0]
        win = tk.Toplevel(self.root)
        win.title("Action–Action matrix (Pi)")
        win.geometry("900x500")

        # Use a text widget to show matrix nicely
        txt = tk.Text(win, wrap="none")
        txt.pack(expand=True, fill="both")
        # header row
        header = "\t" + "\t".join(self.actions) + "\n"
        txt.insert("end", header)
        for i in range(n):
            row_str = self.actions[i] + "\t" + "\t".join(f"{Pi[i,j]:.4f}" for j in range(n)) + "\n"
            txt.insert("end", row_str)

    def _show_flows_window(self):
        phi_plus = self.promethee_results["phi_plus"]
        phi_minus = self.promethee_results["phi_minus"]
        phi = self.promethee_results["phi"]
        n = len(phi)
        win = tk.Toplevel(self.root)
        win.title("Flows (Phi+, Phi-, Phi)")
        win.geometry("600x420")

        txt = tk.Text(win, wrap="none")
        txt.pack(expand=True, fill="both")
        txt.insert("end", "Action\tPhi+\tPhi-\tPhi\n")
        for i in range(n):
            txt.insert("end", f"{self.actions[i]}\t{phi_plus[i]:.4f}\t{phi_minus[i]:.4f}\t{phi[i]:.4f}\n")

    def _show_ranking_window(self):
        phi = self.promethee_results["phi"]
        ranking_idx = self.promethee_results["ranking_idx"]
        win = tk.Toplevel(self.root)
        win.title("Final Ranking")
        win.geometry("500x420")

        txt = tk.Text(win, wrap="none")
        txt.pack(expand=True, fill="both")
        txt.insert("end", "Rank\tAction\tPhi\n")
        for rank, idx in enumerate(ranking_idx, start=1):
            txt.insert("end", f"{rank}\t{self.actions[idx]}\t{phi[idx]:.4f}\n")


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "decider_policeman"
    root = tk.Tk()
    app = DeciderApp(root, name)
    root.mainloop()