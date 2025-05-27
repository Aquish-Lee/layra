type ShowAlert = {
  show: boolean;
  type: string;
  message: string;
};

const Alert = ({showAlert}: {showAlert: ShowAlert}) => {
  return (
    <div
      className={`w-1/5 z-50 fixed top-20 left-1/2 transform -translate-x-1/2 p-4 rounded-3xl text-white text-center shadow-lg transition-opacity duration-300 ease-in-out ${
        showAlert.show ? "opacity-100" : "opacity-0"
      } ${
        showAlert.type === "success"
          ? "bg-gradient-to-r from-indigo-500 to-indigo-600"
          : "bg-gradient-to-r from-red-500 to-red-600"
      } 
            shadow-xl border border-gray-200 animate-bounce`}
    >
      <p className="text-lg font-semibold">{showAlert.message}</p>
    </div>
  );
};

export default Alert;
